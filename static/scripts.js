// static/scripts.js

document.addEventListener('DOMContentLoaded', () => {
  // --- Admin (/admin) ---
  if (location.pathname === '/admin') {
    const folderInput = document.getElementById('folderInput');
    const btnGen      = document.getElementById('btnGenerate');
    const btnExport   = document.getElementById('btnExport');
    const statusG     = document.getElementById('statusGen');
    const prgBar      = document.getElementById('prg');
    const prgText     = document.getElementById('prgText');
    const prgCont     = document.getElementById('progressContainer');
    const csvInput    = document.getElementById('csvInput');
    const btnLoadCSV  = document.getElementById('btnLoadCSV');
    const statusLoad  = document.getElementById('statusLoadCSV');

    // 1) Habilitar “Generar” al seleccionar carpeta
    folderInput.addEventListener('change', () => {
      btnGen.disabled = folderInput.files.length === 0;
    });

    // 1b) Habilitar “Cargar CSV” al seleccionar archivo
    csvInput.addEventListener('change', () => {
      btnLoadCSV.disabled = !csvInput.files.length;
    });

    // 2) Iniciar generación y mostrar progreso
    btnGen.addEventListener('click', () => {
      const fd = new FormData();
      Array.from(folderInput.files).forEach(f => fd.append('files', f));

      // Reset UI
      statusG.textContent = '';
      prgBar.value = 0;
      prgText.textContent = '0%';
      prgCont.style.display = 'block';
      btnGen.disabled = true;
      btnExport.disabled = true;

      // Llamada al servidor
      fetch('/generate', {
        method: 'POST',
        body: fd
      }).then(() => pollProgress());
    });

    // 3) Polling al endpoint de progreso
    function pollProgress() {
      fetch('/progress')
        .then(r => r.json())
        .then(p => {
          const pct = p.total ? Math.floor(100 * p.done / p.total) : 0;
          prgBar.value = pct;
          prgText.textContent = `${pct}%`;

          if (p.state === 'running') {
            setTimeout(pollProgress, 300);
          } else {
            statusG.textContent = 'Dataset cargado y listo para exportar';
            btnExport.disabled = false;
          }
        });
    }

    // 4) Exportar CSV
    btnExport.addEventListener('click', () => {
      window.location.href = '/export';
    });

    // 4b) Cargar dataset desde CSV
    btnLoadCSV.addEventListener('click', () => {
      const fd = new FormData();
      fd.append('files', csvInput.files[0]);
      fetch('/import', { method: 'POST', body: fd })
        .then(r => r.json())
        .then(j => {
          statusLoad.textContent = `Dataset cargado desde CSV (${j.count} filas)`;
          btnExport.disabled = false;
        });
    });
      
  }

  // --- Docs (/docs) ---
  if (location.pathname === '/docs') {
    const root = document.getElementById('bodyContent');

    // 1) Render plantilla inicial
    root.innerHTML = `
      <div class="layout card">
        <aside class="sidebar">
          <h3>Filtros</h3>
          <div class="filter-group">
            <label>Año: <span id="yearRange">–</span></label><br>
            <input type="range" id="fYearMin" disabled>
            <input type="range" id="fYearMax" disabled>
          </div>
          <div class="filter-group">
            <label>Sala:</label><br>
            <select id="fSala" disabled>
              <option value="">--Todas--</option>
            </select>
          </div>
          <div class="filter-group">
            <label>Nro. Documento:</label><br>
            <input type="text" id="fNroDoc" placeholder="Ingresar Nro. Doc.">
          </div>
        </aside>
        <main class="main">
          <h2>Condiciones de búsqueda</h2>
          <div id="searchCriteria">
            <div class="cond">
              <select id="op1"><option>AND</option><option>OR</option><option>NOT</option></select>
              <input type="text" id="ph1" placeholder="Frase 1">
            </div>
            <div class="cond">
              <select id="op2" disabled><option>AND</option><option>OR</option><option>NOT</option></select>
              <input type="text" id="ph2" disabled placeholder="Frase 2">
            </div>
            <div class="cond">
              <select id="op3" disabled><option>AND</option><option>OR</option><option>NOT</option></select>
              <input type="text" id="ph3" disabled placeholder="Frase 3">
            </div>
          </div>
          <button id="btnSearch" disabled>Buscar</button>
          <span id="statusSearch"></span>
          <div id="indicator" style="margin-top:1rem;font-weight:500;"></div>
          <table id="results" style="display:none;">
            <thead>
              <tr>
                <th>URL</th>
                <th>Información General</th>
                <th>Sumilla</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
          <div id="pagination"></div>
        </main>
      </div>
    `;

    // 2) Capturar referencias
    const yearMin   = document.getElementById('fYearMin');
    const yearMax   = document.getElementById('fYearMax');
    const yearRange = document.getElementById('yearRange');
    const salaSel   = document.getElementById('fSala');
    const nroDoc    = document.getElementById("fNroDoc")
    const btnSearch = document.getElementById('btnSearch');
    const statusS   = document.getElementById('statusSearch');
    const indicator = document.getElementById('indicator');
    const tbl       = document.getElementById('results');
    const tbody     = tbl.querySelector('tbody');
    const pagination= document.getElementById('pagination');
    const ops       = [1,2,3].map(i => ({
      op: document.getElementById(`op${i}`),
      ph: document.getElementById(`ph${i}`)
    }));
    let allResults = [];

    // 3) Habilitar filas de condiciones encadenadas
    ops.forEach((o,i) => {
      o.ph.addEventListener('input', e => {
        if (e.target.value.trim() && i < 2) {
          ops[i+1].op.disabled = false;
          ops[i+1].ph.disabled = false;
        }
        btnSearch.disabled = !ops[0].ph.value.trim();
      });
    });

    // 4) Función de paginado
    function renderPage(page) {
      const perPage = 20;
      const start   = (page-1)*perPage;
      const slice   = allResults.slice(start, start+perPage);

      tbody.innerHTML = '';

      slice.forEach(row => {
        const tr = tbody.insertRow();
      
        // 1. URL con icono PDF
        const tdUrl = tr.insertCell();
        const aUrl = document.createElement('a');
        aUrl.href = `https://spo-global.kpmg.com/sites/PE-TAXLAB/TA_BuscadorDocumentos/${encodeURIComponent(row['Nombre'])}`;
        aUrl.target = '_blank';
        aUrl.rel = 'noopener noreferrer';
      
        const img = document.createElement('img');
        img.src = 'static/img/pdf-icon.png';
        img.alt = 'PDF';
        img.width = 32;
      
        aUrl.appendChild(img);
        tdUrl.appendChild(aUrl);
      
        // 2. Información General (card)
        const tdInfo = tr.insertCell();
        const card = document.createElement('div');
        card.className = 'info-card';
        card.innerHTML = `
          <strong>${row['Nombre'] || ''}</strong><br>
          <span>Asunto:</span> ${row['Asunto'] || ''}<br>
          <span>Año:</span> ${row['Año'] || ''}<br>
          <span>Sala:</span> ${row['Sala'] || ''}<br>
          <span>NroDoc:</span> ${row['Nro Documento'] || ''}<br>
          <span>Fecha:</span> ${row['Fecha'] || ''}
        `;
        tdInfo.appendChild(card);
      
        // 3. Sumilla
        const tdSumilla = tr.insertCell();
        tdSumilla.textContent = row['Sumilla'] || '';
      }); 
    
      /* paginador – sin cambios */
      tbl.style.display = slice.length ? '' : 'none';
      pagination.innerHTML = '';
      const totalPages = Math.ceil(allResults.length / perPage);
      for (let p = 1; p <= totalPages; p++) {
        const btn = document.createElement('button');
        btn.textContent = p;
        btn.disabled = p === page;
        btn.addEventListener('click', () => renderPage(p));
        pagination.appendChild(btn);
      }
      
    }

    // 5) Manejador de búsqueda
    btnSearch.addEventListener('click', () => {
      statusS.textContent = 'Buscando…';
      const condiciones = ops
        .filter(o => o.ph.value.trim())
        .map(o => [o.ph.value.trim(), o.op.value]);
      const filtros = {
        AñoMin: yearMin.value,
        AñoMax: yearMax.value,
        Sala:   salaSel.value,
        NroDoc: nroDoc.value
      };
      fetch('/search', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({conditions: condiciones, filters: filtros})
      })
      .then(r => r.json())
      .then(j => {
        allResults = j.results;
        statusS.textContent = '';
        if (!allResults.length) {
          indicator.textContent = 'No se han encontrado resultados';
          tbl.style.display = 'none';
          pagination.innerHTML = '';
        } else {
          indicator.textContent = `Resultados: ${allResults.length}`;
          renderPage(1);
        }
      });
    });

    // 6) Inicializar filtros con metadata
    fetch('/metadata')
      .then(r => r.json())
      .then(meta => {
        if (!meta.loaded) {
          root.innerHTML = '<p style="font-weight:500">No hay información disponible.</p>';
          return;
        }
        // Configurar rango de años
        yearMin.min = meta.minYear; yearMin.max = meta.maxYear;
        yearMax.min = meta.minYear; yearMax.max = meta.maxYear;
        yearMin.value = meta.minYear; yearMax.value = meta.maxYear;
        yearRange.textContent = `${meta.minYear} – ${meta.maxYear}`;
        [yearMin, yearMax].forEach(inp => {
          inp.disabled = false;
          inp.addEventListener('input', () => {
            const minv = Math.min(+yearMin.value, +yearMax.value),
                  maxv = Math.max(+yearMin.value, +yearMax.value);
            yearRange.textContent = `${minv} – ${maxv}`;
            btnSearch.disabled = !ops[0].ph.value.trim();
          });
        });
        // Poblar select de Sala
        salaSel.disabled = false;
        meta.salas.forEach(s => {
          const opt = document.createElement('option');
          opt.value = s; opt.textContent = s;
          salaSel.appendChild(opt);
        });
        btnSearch.disabled = !ops[0].ph.value.trim();
      });
  }
});
