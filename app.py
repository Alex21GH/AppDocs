import os, csv, json, io, mimetypes, cgi, sys
import pandas as pd
from http.server import HTTPServer, BaseHTTPRequestHandler
import ssl
from http.server import HTTPServer
from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError
import threading
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# Estado del progreso
PROGRESS = {
    'total': 0,
    'done': 0,
    'state': 'idle'  # 'idle' | 'running' | 'done'
}

global DATASET
DATASET = []

def generar_dataset(directorio):
    global DATASET
    DATASET = []
    for fn in os.listdir(directorio):
        if fn.lower().endswith('.pdf'):
            try:
                texto = ''
                reader = PdfReader(os.path.join(directorio, fn))
                for p in reader.pages:
                    texto += p.extract_text() or ''
                if texto.strip():
                    DATASET.append({'Nombre': fn, 'contenido': texto})
            except (PdfReadError, PdfStreamError):
                pass
    return len(DATASET)


def importar_dataset_csv(fileobj):

    # Increase the field size limit
    csv.field_size_limit(sys.maxsize)

    text = io.TextIOWrapper(fileobj, encoding='utf-8', newline='')
    reader = csv.DictReader(text, delimiter=';')

    # Lee la primera línea y verifica si tiene encabezados
    first_line = text.readline()
    if 'Nombre' in first_line:
        # Tiene encabezados
        text.seek(0)
        reader = csv.DictReader(text, delimiter=';')
    else:
        # No tiene encabezados: define los tuyos
        headers = ['Nombre','Año','Sala','Nro Documento','Asunto','Sumilla','Fecha','contenido']
        reader = csv.DictReader(io.StringIO(first_line + text.read()), delimiter=';', fieldnames=headers)
    for row in reader:
        def g(*keys):
            for k in keys:
                if k in row: return row[k]
            return ''
        raw_year = g('Año')
        año_val = int(raw_year) if str(raw_year).isdigit() else None
        DATASET.append({
            'Nombre': g('Nombre'),
            'contenido': g('contenido', 'Contenido'),
            'Sumilla': g('Sumilla'),
            'Asunto': g('Asunto'),
            'Año': año_val,
            'Sala': g('Sala'),
            'Nro Documento': g('Nro Documento', 'NroDocumento'),
            'Fecha': g('Fecha')
        })
    return len(DATASET)


def buscar_en_dataset(condiciones, filtros):
    resultados = []
    for entry in DATASET:
        # Obtener valores del dataset
        filename = entry['Nombre']
        txt = entry['contenido']
        ok = True

        # Iniciar busqueda
        for frase, op in condiciones:
            if   op=='AND' and frase not in txt: ok=False; break
            elif op=='NOT' and frase in txt:       ok=False; break
            elif op=='OR'  and frase in txt:       ok=True
        
        if not ok:
            continue

        # filtros opcionales por año y sala
        año_num = entry.get('Año')  # int o None
        if año_num is not None:
            if filtros.get('AñoMin') and año_num < int(filtros['AñoMin']):
                continue
            if filtros.get('AñoMax') and año_num > int(filtros['AñoMax']):
                continue
        if filtros.get('NroDoc') and filtros['NroDoc']:  # evaluar existencia de filtro 
            print(f"Entry: {entry.get('Nro Documento')} - Filter value: {filtros['NroDoc']}")
            if filtros['NroDoc'] not in entry.get('Nro Documento'): continue                          
        # if substring in main_string
        if filtros.get('Sala') and filtros['Sala']:
            if entry.get('Sala') != filtros['Sala']: continue


        resultados.append(entry)
        """
        # aplicar filtros later sobre metadatos (por ahora solo Nombre)
        if ok:
            resultados.append({
                'Nombre': entry['Nombre'], 
                'Sumilla':'','Asunto':'','Año':'','Sala':'','Nro Documento':'','Fecha':''
            })
        """
    # aquí podrías filtrar por filtros['Año'], filtros['Asunto'], filtros['Sala']
    return resultados


def _limpiar_texto(txt: str) -> str:
        txt = re.sub(r"[^\w\s\-]", " ", txt)
        return re.sub(r"\s{2,}", " ", txt)

MESES = {
    "enero":"01","febrero":"02","marzo":"03","abril":"04","mayo":"05","junio":"06",
    "julio":"07","agosto":"08","septiembre":"09","octubre":"10","noviembre":"11","diciembre":"12"
}

def _convertir_fecha(fecha_str: str) -> str:
    m = re.match(r"(\d{1,2}) de ([a-zA-Z]+) de (\d{4})", fecha_str, re.I)
    if not m:
        return ""
    dia, mes, anio = m.groups()
    return f"{anio}-{MESES.get(mes.lower(),'01')}-{int(dia):02d}"   # AAAA-MM-DD

def _extraer_asunto_fecha(texto: str):
    """Devuelve (asunto, fecha) usando las mismas regex que el script GUI."""
    texto = _limpiar_texto(texto)
    # Asunto
    m_asunto = re.search(r"ASUNTO\s*[:!–-]?\s*(.+?)\s*(PROCEDENCIA|FECHA|VISTA)", texto, re.S)
    asunto = m_asunto.group(1).strip() if m_asunto else ""
    # Fecha
    m_fecha = re.search(r"FECHA\s*[:l]?\s*.*?(\d{1,2} de [a-zA-Z]+ de \d{4})", texto, re.S)
    fecha = _convertir_fecha(m_fecha.group(1)) if m_fecha else ""
    return asunto, fecha

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(302)
            self.send_header('Location', '/docs')
            self.end_headers()
            return
        elif self.path=='/admin':
            self._serve_file('static/admin.html','text/html')
        elif self.path=='/docs':
            self._serve_file('static/docs.html','text/html')
        elif self.path.startswith('/static/'):
            path = self.path.lstrip('/')
            self._serve_file(path)
        elif self.path == '/metadata':
            # Devuelve estado, rango de años y salas únicas
            loaded = bool(DATASET)
            # Extrae años y salas de los metadatos del dataset
            years = sorted({row['Año'] for row in DATASET if isinstance(row.get('Año'), int)})
            salas = sorted({row.get('Sala') for row in DATASET if row.get('Sala')})
            self._json_response({
                'loaded': loaded,
                'minYear': years[0] if years else None,
                'maxYear': years[-1] if years else None,
                'salas': salas
            })
        elif self.path == '/export':
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename="dataset.csv"')
            self.end_headers()
            import io
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(['Nombre','Sumilla','Asunto','Año','Sala','Nro Documento','Fecha','Contenido'])
            for row in DATASET:
                contenido_limpio = row.get('contenido', '').replace('\n', ' ').replace('\r', ' ').strip()
                w.writerow([
                    row['Nombre'],
                    row.get('Sumilla',''),
                    row.get('Asunto',''),
                    row.get('Año',''),
                    row.get('Sala',''),
                    row.get('Nro Documento',''),
                    row.get('Fecha',''),
                    contenido_limpio
                ])
            # Escribe todo de una vez como bytes
            self.wfile.write(buf.getvalue().encode('utf-8'))

        elif self.path == '/progress':
            # Nuevo endpoint para consultar progreso de carga
            self._json_response(PROGRESS)

        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers['Content-Length'])
        body = self.rfile.read(length)
        if self.path == '/generate':
            # Extrae múltiples archivos del form-data
            file_fields = self._extract_files_from_multipart(body, self.headers['Content-Type'])
            # Inicializa estado de progreso
            PROGRESS.update({'total': len(file_fields), 'done': 0, 'state': 'running'})
            # Lanza hilo para procesar sin bloquear
            threading.Thread(
                target=self._generate_from_upload,
                args=(file_fields,),
                daemon=True
            ).start()
            self._json_response({'status': 'INICIADO'})

        elif self.path=='/import':
            files = self._extract_files_from_multipart(body, self.headers['Content-Type'])
            fileobj = files[0].file
            cnt = importar_dataset_csv(fileobj)
            # Log en servidor
            print(f"Dataset cargado desde CSV: {cnt} filas")
            df_preview = pd.DataFrame(DATASET)
            print(df_preview.drop(columns=['contenido'], errors='ignore').head())
            self._json_response({'status':'LISTO','count':cnt})
        elif self.path=='/search':
            data = json.loads(body)
            conds = data.get('conditions',[])
            filtros = data.get('filters',{})
            res = buscar_en_dataset(conds, filtros)
            self._json_response({'results':res})
        # Nuevo endpoint para consultar progreso
        elif self.path == '/progress':
            self._json_response(PROGRESS)
        else:
            self.send_error(404)


    def _generate_from_upload(self, file_fields):
        """Procesa cada PDF subido, extrae texto y actualiza PROGRESS."""
        global DATASET
        DATASET = []
        for fs in file_fields:
            raw = fs.filename
            filename = os.path.basename(raw)

            reader = PdfReader(fs.file)
            text_pages = ""
            for p_idx, pg in enumerate(reader.pages[:10]):         # máximo 10 páginas
                text_pages += pg.extract_text() or ""
            asunto, fecha = _extraer_asunto_fecha(text_pages)

            # Extraer metadatos del nombre
            año = None
            if len(filename) >= 4 and filename[:4].isdigit():
                año = int(filename[:4])
            
            sala = filename[5] if len(filename) >= 6 else ''
            idx_pdf = filename.lower().rfind('.pdf')
            nro = filename[7:idx_pdf] if idx_pdf >= 7 else ''
            try:
                reader = PdfReader(fs.file)
                texto = ''
                for p in reader.pages:
                    texto += p.extract_text() or ''
                if texto.strip():
                    DATASET.append({
                        'Nombre': filename,
                        'contenido': texto,
                        'Año': año,
                        'Sala': sala,
                        'Nro Documento': nro,
                        'Asunto': asunto,
                        'Fecha': fecha
                    })
            except Exception:
                pass
            PROGRESS['done'] += 1

        print(f"Dataset cargado: {len(DATASET)} filas")
        df_preview = pd.DataFrame(DATASET)
        print(df_preview.drop(columns=['contenido'], errors='ignore').head())
        PROGRESS['state'] = 'done'

    
    # Helpers
    def _serve_file(self, path, content_type=None):
        try:
            with open(path,'rb') as f: data = f.read()
            self.send_response(200)
            ctype = content_type or mimetypes.guess_type(path)[0] or 'application/octet-stream'
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', len(data))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404,f'No existe {path}')

    def _json_response(self, obj, status=200):
        payload = json.dumps(obj).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',len(payload))
        self.end_headers()
        self.wfile.write(payload)
    
    def _extract_files_from_multipart(self, body, ctype_hdr):
        import io, cgi
        fp = io.BytesIO(body)
        env = {'REQUEST_METHOD':'POST','CONTENT_TYPE':ctype_hdr,'CONTENT_LENGTH':str(len(body))}
        fs = cgi.FieldStorage(fp=fp, environ=env, keep_blank_values=True)
        files = fs['files']
        return files if isinstance(files, list) else [files]


if __name__=='__main__':
    #ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    #ctx.load_cert_chain(certfile='cert.pem', keyfile='key.pem')

    #httpd = HTTPServer(('0.0.0.0', 443), Handler)
    #httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

    #httpd.serve_forever()
    
    srv = HTTPServer(('localhost',8000),Handler)
    print("Arrancando en http://localhost:8000/docs")
    srv.serve_forever()
