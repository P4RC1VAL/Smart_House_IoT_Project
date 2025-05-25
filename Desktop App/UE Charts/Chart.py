import firebase_admin
from firebase_admin import credentials, db
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime


def init_firebase():
    cred = credentials.Certificate(r"C:\Users\makla\Downloads\smarthouseai-firebase-adminsdk-fbsvc-15053274af.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://smarthouseai-default-rtdb.europe-west1.firebasedatabase.app/'
    })


def get_firebase_data():
    ref = db.reference('Data')
    snapshot = ref.get()

    if isinstance(snapshot, dict) and 'Data' in snapshot:
        return snapshot
    else:
        raise ValueError("Неверная структура данных")


def plot_all_metrics(data):
    try:
        timestamps = [datetime.fromisoformat(entry['timestamp']) for entry in data['Data']]

        # Создаем сетку графиков 2x2
        fig, axs = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Показатели сенсоров', fontsize=16, y=1.02)

        # Температура
        axs[0, 0].plot(timestamps, [e['temperature'] for e in data['Data']], 'o-', color='tab:red')
        axs[0, 0].set_title('Температура')
        axs[0, 0].set_ylabel('°C')

        # Влажность
        axs[0, 1].plot(timestamps, [e['humidity'] for e in data['Data']], 'o-', color='tab:blue')
        axs[0, 1].set_title('Влажность')
        axs[0, 1].set_ylabel('%')

        # CO2
        axs[1, 0].plot(timestamps, [e['co2'] for e in data['Data']], 'o-', color='tab:green')
        axs[1, 0].set_title('CO2')
        axs[1, 0].set_ylabel('ppm')

        # Давление
        axs[1, 1].plot(timestamps, [e['pressure'] for e in data['Data']], 'o-', color='tab:purple')
        axs[1, 1].set_title('Давление')
        axs[1, 1].set_ylabel('гПа')

        # Форматирование для всех графиков
        for ax in axs.flat:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=5))
            ax.grid(alpha=0.3)
            plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

        plt.tight_layout()
        plt.show()

    except KeyError as e:
        print(f"Ошибка: Отсутствует ключ {e}")
    except Exception as e:
        print(f"Ошибка построения: {str(e)}")


if __name__ == "__main__":
    init_firebase()
    try:
        firebase_data = get_firebase_data()
        plot_all_metrics(firebase_data)
    except Exception as e:
        print(f"Ошибка: {str(e)}")




@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Real-time Charts</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
        <style>
            /* Сохраните предыдущие стили */
        </style>
    </head>
    <body>
        <h1>Показатели датчиков</h1>
        <div class="chart-grid" id="charts"></div>

        <script>
        const charts = {};

        function createChart(containerId, title, yTitle) {
            charts[containerId] = {
                layout: {
                    title: title,
                    margin: {t: 40, l: 60, r: 30, b: 60},
                    xaxis: {title: 'Время', type: 'date', gridcolor: '#444'},
                    yaxis: {title: yTitle, gridcolor: '#444'},
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    font: {color: '#FFF'}
                },
                config: {responsive: true}
            };

            Plotly.newPlot(
                containerId, 
                [{x: [], y: [], type: 'scatter', line: {color: '#4CAF50'}}],
                charts[containerId].layout,
                charts[containerId].config
            );
        }

        const socket = io();

        socket.on('connect', () => {
            console.log('Connected to WebSocket');
            initCharts();
        });

        socket.on('data_update', function(data) {
            updateCharts(data);
        });

        function initCharts() {
            const containers = {
                'tempChart': ['Температура', '°C'],
                'humidityChart': ['Влажность', '%'],
                'co2Chart': ['CO₂', 'ppm'],
                'pressureChart': ['Давление', 'гПа']
            };

            document.getElementById('charts').innerHTML = '';

            Object.entries(containers).forEach(([id, [title, unit]]) => {
                const div = document.createElement('div');
                div.id = id;
                div.className = 'chart';
                document.getElementById('charts').appendChild(div);
                createChart(id, title, unit);
            });
        }

        function updateCharts(data) {
            Object.keys(charts).forEach(chartId => {
                const type = chartId.replace('Chart', '');
                Plotly.react(chartId, [{
                    x: data.timestamps,
                    y: data[type]
                }], charts[chartId].layout);
            });
        }
        </script>
    </body>
    </html>
    ''')