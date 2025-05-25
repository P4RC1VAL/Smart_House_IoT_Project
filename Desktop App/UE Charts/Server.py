import eventlet

eventlet.monkey_patch()

from flask import Flask, render_template_string
from flask_socketio import SocketIO
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db
import logging
import traceback
from datetime import datetime

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')


def initialize_firebase():
    try:
        cred = credentials.Certificate(r"C:\Users\makla\Downloads\smarthouse-3760c-firebase-adminsdk-fbsvc-d8658807c2.json")
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://smarthouse-3760c-default-rtdb.asia-southeast1.firebasedatabase.app/'
        })
        logger.info("Firebase initialized successfully")
    except Exception as e:
        logger.error(f"Firebase init error: {str(e)}")
        raise


initialize_firebase()


def parse_firebase_data(raw_data):
    try:
        entries = []
        # Обрабатываем структуру sensors/HIST/{timestamp}
        if isinstance(raw_data, dict):
            for timestamp_str, values in raw_data.items():
                if isinstance(values, dict):
                    entry = {
                        'timestamp': values.get('timestamp', timestamp_str),
                        'temperature': values.get('temperature'),
                        'humidity': values.get('humidity'),
                        'co2': values.get('co2'),
                        'pressure': values.get('pressure')
                    }
                    entries.append(entry)

        # Сортируем по времени
        entries.sort(key=lambda x: x['timestamp'])

        return {
            'timestamps': [e['timestamp'] for e in entries],
            'temperature': [e['temperature'] for e in entries],
            'humidity': [e['humidity'] for e in entries],
            'co2': [e['co2'] for e in entries],
            'pressure': [e['pressure'] for e in entries]
        }
    except Exception as e:
        logger.error(f"Parse error: {str(e)}")
        return None


def firebase_listener(event):
    try:
        logger.info(f"Event received: {event.event_type} at path {event.path}")

        # Получаем полный путь к данным
        ref = db.reference('sensors/HIST')
        snapshot = ref.get()

        data = parse_firebase_data(snapshot)
        if data:
            socketio.emit('update', data)
    except Exception as e:
        logger.error(f"Listener error: {str(e)}")


def firebase_watcher():
    while True:
        try:
            ref = db.reference('sensors/HIST')
            logger.info("Starting Firebase listener for sensors/HIST...")
            ref.listen(firebase_listener)
        except Exception as e:
            logger.error(f"Watcher error: {str(e)}, retrying in 5s...")
            eventlet.sleep(5)


@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Compact Charts</title>
        <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
        <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
        <style>
            body {
                margin: 0;
                padding: 0;
                background: rgba(0,0,0,0);
                overflow: hidden;
            }
            .chart-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 2px;
                width: 100vw;
                height: 100vh;
                padding: 2px;
                box-sizing: border-box;
            }
            .chart-container {
                width: 100%!important;
                height: 80%!important;
                min-width: 0;
                min-height: 0;
            }
        </style>
    </head>
    <body>
        <div class="chart-grid">
            <div id="temperatureChart" class="chart-container"></div>
            <div id="humidityChart" class="chart-container"></div>
            <div id="co2Chart" class="chart-container"></div>
            <div id="pressureChart" class="chart-container"></div>
        </div>

        <script>
            const socket = io();
    
            // Конфигурация графиков
            const chartConfigs = {
                temperatureChart: {
                    title: 'Температура',
                    yTitle: '°C',
                    color: '#FF6B6B'
                },
                humidityChart: {
                    title: 'Влажность',
                    yTitle: '%',
                    color: '#4D8AF0'
                },
                co2Chart: {
                    title: 'Уровень CO₂',
                    yTitle: 'ppm',
                    color: '#34D399'
                },
                pressureChart: {
                    title: 'Атмосферное давление',
                    yTitle: 'гПа',
                    color: '#F9A825'
                }
            };
        
            // Инициализация графиков
            function initChart(divId, config) {
                const layout = {
                    title: {
                        text: config.title,
                        font: {
                            color: '#FFF',
                            size: 18,
                            family: 'Arial'
                        },
                        x: 0.05, // Выравнивание по левому краю
                        y: 0.95  // Позиция относительно верхнего края
                    },
                    xaxis: {
                        title: {
                            text: 'Время',
                            font: {
                                color: '#FFF',
                                size: 14
                            }
                        },
                        type: 'date',
                        gridcolor: '#555',
                        tickfont: {
                            color: '#FFF'
                        },
                        zerolinecolor: '#555'
                    },
                    yaxis: {
                        title: {
                            text: config.yTitle,
                            font: {
                                color: '#FFF',
                                size: 14
                            }
                        },
                        gridcolor: '#555',
                        tickfont: {
                            color: '#FFF'
                        },
                        zerolinecolor: '#555'
                    },
                    margin: {t: 60, l: 80, r: 30, b: 80},
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    showlegend: false
                };
        
                Plotly.newPlot(divId, [{
                    x: [],
                    y: [],
                    type: 'scatter',
                    line: {color: config.color},
                    hoverinfo: 'x+y'
                }], layout);
            }
        
            // Обновление данных
            function updateChart(divId, xData, yData) {
                Plotly.react(divId, [{
                    x: xData,
                    y: yData,
                    type: 'scatter',
                    line: {color: chartConfigs[divId].color}
                }], {
                    title: {
                        text: chartConfigs[divId].title
                    },
                    yaxis: {
                        title: {
                            text: chartConfigs[divId].yTitle
                        }
                    }
                });
            }
        
            // Инициализация всех графиков
            function initAllCharts() {
                Object.keys(chartConfigs).forEach(divId => {
                    initChart(divId, chartConfigs[divId]);
                });
            }
        
            // Обработчик обновлений
            socket.on('update', function(data) {
                if (!data) return;
                
                try {
                    const timestamps = data.timestamps.map(t => new Date(t));
                    
                    Object.keys(chartConfigs).forEach(divId => {
                        const metric = divId.replace('Chart', '');
                        updateChart(divId, timestamps, data[metric]);
                    });
                } catch(e) {
                    console.error('Ошибка обновления:', e);
                }
            });
        
            // Запуск при загрузке
            window.addEventListener('DOMContentLoaded', initAllCharts);
        </script>
    </body>
    </html>
    ''')


if __name__ == '__main__':
    eventlet.spawn(firebase_watcher)
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)