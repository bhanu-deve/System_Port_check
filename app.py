from flask import Flask, jsonify, render_template_string, url_for
import subprocess
import re

app = Flask(__name__)

def is_system_port(port):
    # Ports 0-1024 inclusive marked as system ports
    return 0 <= port <= 1024

def get_netstat_output():
    result = subprocess.run(['netstat', '-aon'], capture_output=True, text=True)
    return result.stdout

def get_tasklist_output():
    result = subprocess.run(['tasklist'], capture_output=True, text=True)
    return result.stdout

def parse_netstat(netstat_output):
    port_pid_map = {}
    for line in netstat_output.splitlines():
        # Match lines with TCP LISTENING and extract port and PID
        match = re.search(r'TCP\s+[\d\.]+:(\d+)\s+[\d\.]+:\d+\s+LISTENING\s+(\d+)', line)
        if match:
            port = int(match.group(1))
            pid = match.group(2)
            port_pid_map[port] = pid
    return port_pid_map

def parse_tasklist(tasklist_output):
    pid_name_map = {}
    # Skip header lines (usually 3 lines)
    for line in tasklist_output.splitlines()[3:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            name = parts[0]
            pid = parts[1]
            pid_name_map[pid] = name
    return pid_name_map

@app.route("/api/ports")
def ports_api():
    netstat_output = get_netstat_output()
    tasklist_output = get_tasklist_output()
    port_pid_map = parse_netstat(netstat_output)
    pid_name_map = parse_tasklist(tasklist_output)

    data = []
    checked_ports = set()

    # Occupied ports from netstat
    for port, pid in sorted(port_pid_map.items()):
        data.append({
            "port": port,
            "systemPort": is_system_port(port),
            "status": "Occupied",
            "software": pid_name_map.get(pid, "Unknown")
        })
        checked_ports.add(port)

    # Add free ports in the full system port range 0-1024
    for port in range(0, 1025):
        if port not in checked_ports:
            data.append({
                "port": port,
                "systemPort": is_system_port(port),
                "status": "Free",
                "software": "-"
            })

    # Sort all entries by port number ascending
    data.sort(key=lambda x: x['port'])

    return jsonify(data)

# Main dashboard page
@app.route("/")
def index():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Port & Software Dashboard</title>
<link rel="icon" type="static/png" href="{{ url_for('static', filename='logo.png') }}">
<style>
  body {
    font-family: Arial, sans-serif;
    margin: 2rem;
    background: #f8f9fa;
  }
  h1 {
    text-align: center;
  }
  input[type=number] {
    width: 200px;
    padding: 8px;
    margin-bottom: 12px;
    border-radius: 5px;
    border: 1px solid #ccc;
    font-size: 1rem;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    background: #fff;
  }
  th, td {
    padding: 10px;
    border-bottom: 1px solid #ddd;
    text-align: left;
  }
  thead {
    background: #007bff;
    color: white;
  }
  tbody tr:hover {
    background-color: #f1f1f1;
  }
  .chip {
    display: inline-block;
    padding: 5px 12px;
    border-radius: 15px;
    color: white;
    font-weight: bold;
    font-size: 0.85rem;
  }
  .system {
    background-color: #1976d2;
  }
  .user {
    background-color: #616161;
  }
  .occupied {
    background-color: #d32f2f;
  }
  .free {
    background-color: #388e3c;
  }
  #loading {
    text-align: center;
    margin-top: 3rem;
    font-weight: bold;
  }
  /* Logo styling */
  .logo-container {
    text-align: center;
    margin-bottom: 1rem;
  }
  .logo-container img {
    height: 200px;
    margin-bottom: 0.5rem;
  }
</style>
</head>
<body>
<div class="logo-container">
  <img src="{{ url_for('static', filename='logo.png') }}" alt="Logo" />
</div>

<h1>Port & Software Dashboard (Real-Time)</h1>

<label for="filterPort">Find port number: </label>
<input type="number" id="filterPort" min="0" max="65535" placeholder="Enter port to filter..." />
<div id="loading">Loading data...</div>
<table id="portTable" style="display:none;">
<thead>
<tr>
  <th>Port Number</th>
  <th>System Port?</th>
  <th>Status</th>
  <th>Software / Process</th>
</tr>
</thead>
<tbody id="tableBody"></tbody>
</table>

<script>
async function fetchPortData() {
  const resp = await fetch('/api/ports');
  const data = await resp.json();
  return data;
}

function createChip(text, className) {
  const span = document.createElement('span');
  span.textContent = text;
  span.className = 'chip ' + className;
  return span;
}

function renderTable(data) {
  const tbody = document.getElementById('tableBody');
  tbody.innerHTML = '';

  if(data.length === 0) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 4;
    td.style.textAlign = 'center';
    td.textContent = 'No ports match your filter.';
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }

  data.forEach(item => {
    const tr = document.createElement('tr');

    // Port
    const tdPort = document.createElement('td');
    tdPort.textContent = item.port;
    tr.appendChild(tdPort);

    // System Port
    const tdSys = document.createElement('td');
    const chipSys = createChip(item.systemPort ? 'System Port' : 'User Port', item.systemPort ? 'system' : 'user');
    tdSys.appendChild(chipSys);
    tr.appendChild(tdSys);

    // Status
    const tdStatus = document.createElement('td');
    const chipStatus = createChip(item.status, item.status.toLowerCase());
    tdStatus.appendChild(chipStatus);
    tr.appendChild(tdStatus);

    // Software
    const tdSoftware = document.createElement('td');
    tdSoftware.textContent = item.software;
    tr.appendChild(tdSoftware);

    tbody.appendChild(tr);
  });
}

document.getElementById('filterPort').addEventListener('input', (event) => {
  const val = event.target.value.trim();
  if (!window._allData) return;

  if (val === '') {
    renderTable(window._allData);
  } else {
    // Filter ports starting with the entered string (port prefix)
    const filtered = window._allData.filter(item => item.port.toString().startsWith(val));
    renderTable(filtered);
  }
});

async function init() {
  const loading = document.getElementById('loading');
  const table = document.getElementById('portTable');
  try {
    loading.style.display = 'block';
    table.style.display = 'none';
    window._allData = await fetchPortData();
    renderTable(window._allData);
    loading.style.display = 'none';
    table.style.display = 'table';
  } catch(e) {
    loading.textContent = 'Failed to load data.';
  }
}

// Initial data load
init();

// Auto refresh every 30 seconds
setInterval(init, 30000);
</script>
</body>
</html>
    ''')

if __name__ == '__main__':
    app.run(debug=True)
