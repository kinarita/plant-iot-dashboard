from bottle import route, run, template, request, static_file, response
import sqlite3
from datetime import datetime, timedelta
import json
import re

@route('/static/<filename:path>')
def send_static(filename):
    return static_file(filename, root='static')

def format_timestamp(timestamp_str, format_type="clean", range_param="24h", data_count=0, screen_width=1200):
    """高度なタイムスタンプフォーマット制御"""
    
    # 基本的な秒以下カット
    if '.' in timestamp_str:
        base_timestamp = timestamp_str.split('.')[0]
    else:
        base_timestamp = timestamp_str
    
    try:
        dt = datetime.fromisoformat(base_timestamp)
        now = datetime.now()
        
        # 集計方法による基本フォーマット
        if format_type == "raw":
            # 生データ: 表示期間と画面幅に応じて調整
            if range_param in ["1h", "6h"]:
                # 短期間: 時:分:秒
                return dt.strftime("%H:%M:%S")
            elif range_param in ["12h", "24h"]:
                # 中期間: 月-日 時:分
                return dt.strftime("%m-%d %H:%M")
            elif range_param in ["3d", "7d"]:
                # 長期間: 月-日 時:分
                return dt.strftime("%m-%d %H:%M")
            else:  # 30d
                # 超長期: 月-日のみ
                return dt.strftime("%m-%d")
                
        elif format_type == "hourly":
            # 時間平均: 時間まで
            if range_param in ["1h", "6h", "12h", "24h"]:
                return dt.strftime("%m-%d %H:00")
            elif range_param in ["3d", "7d"]:
                return dt.strftime("%m-%d %H:00")
            else:  # 30d
                return dt.strftime("%m-%d")
                
        elif format_type == "daily":
            # 日平均: 日付のみ
            return dt.strftime("%m-%d")
            
        # データ点数による動的調整
        if data_count > 50:
            # データが多い場合は簡略化
            if range_param in ["1h", "6h"]:
                return dt.strftime("%H:%M")
            else:
                return dt.strftime("%m-%d")
        
        # 画面幅による調整
        if screen_width < 768:  # モバイル
            if range_param in ["1h", "6h"]:
                return dt.strftime("%H:%M")
            else:
                return dt.strftime("%m-%d")
        
        return base_timestamp
        
    except Exception:
        # パース失敗時は基本カット版を返す
        return base_timestamp

def get_optimal_time_format(range_param, aggregate_param, data_count, screen_width=1200):
    """最適な時間表示形式を決定"""
    
    format_rules = {
        # 生データの場合
        "raw": {
            "1h": {"format": "%H:%M:%S", "max_ticks": 12},
            "6h": {"format": "%H:%M", "max_ticks": 15},
            "12h": {"format": "%m-%d %H:%M", "max_ticks": 12},
            "24h": {"format": "%m-%d %H:%M", "max_ticks": 15},
            "3d": {"format": "%m-%d %H:%M", "max_ticks": 10},
            "7d": {"format": "%m-%d %H:%M", "max_ticks": 8},
            "30d": {"format": "%m-%d", "max_ticks": 10}
        },
        # 時間平均の場合
        "hourly": {
            "1h": {"format": "%H:00", "max_ticks": 12},
            "6h": {"format": "%H:00", "max_ticks": 12},
            "12h": {"format": "%H:00", "max_ticks": 12},
            "24h": {"format": "%m-%d %H:00", "max_ticks": 12},
            "3d": {"format": "%m-%d %H:00", "max_ticks": 10},
            "7d": {"format": "%m-%d %H:00", "max_ticks": 8},
            "30d": {"format": "%m-%d", "max_ticks": 10}
        },
        # 日平均の場合
        "daily": {
            "1h": {"format": "%m-%d", "max_ticks": 1},
            "6h": {"format": "%m-%d", "max_ticks": 1},
            "12h": {"format": "%m-%d", "max_ticks": 1},
            "24h": {"format": "%m-%d", "max_ticks": 1},
            "3d": {"format": "%m-%d", "max_ticks": 3},
            "7d": {"format": "%m-%d", "max_ticks": 7},
            "30d": {"format": "%m-%d", "max_ticks": 10}
        }
    }
    
    rule = format_rules.get(aggregate_param, format_rules["raw"]).get(range_param, {"format": "%m-%d %H:%M", "max_ticks": 10})
    
    # データ点数による調整
    if data_count > 100:
        rule["max_ticks"] = min(rule["max_ticks"], 8)
    elif data_count > 50:
        rule["max_ticks"] = min(rule["max_ticks"], 12)
    
    # 画面幅による調整
    if screen_width < 768:  # モバイル
        rule["max_ticks"] = min(rule["max_ticks"], 6)
        # モバイルでは短縮形式
        if rule["format"] == "%m-%d %H:%M":
            rule["format"] = "%m-%d %H"
        elif rule["format"] == "%m-%d %H:00":
            rule["format"] = "%m-%d"
    
    return rule

@route('/')
def index():
    # クエリパラメータから設定を取得
    range_param = request.query.range or "24h"
    aggregate_param = request.query.aggregate or "raw"
    location_param = request.query.location or "all"  # センサー場所フィルター
    screen_width = int(request.query.width or "1200")  # JavaScript から画面幅を受信
    
    # 時間条件の設定
    time_conditions = {
        "1h": "datetime('now', '-1 hours')",
        "6h": "datetime('now', '-6 hours')",
        "12h": "datetime('now', '-12 hours')",
        "24h": "datetime('now', '-1 days')",
        "3d": "datetime('now', '-3 days')",
        "7d": "datetime('now', '-7 days')",
        "30d": "datetime('now', '-30 days')"
    }
    
    time_condition = time_conditions.get(range_param, time_conditions["24h"])
    
    conn = sqlite3.connect("sensor_data.db")
    cursor = conn.cursor()
    
    # テーブル名を確認して適切なものを使用
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    # 実際のテーブル名を特定
    table_name = "sensor_data"  # デフォルト（正しいスペル）
    if "sensor_data" in tables:
        table_name = "sensor_data"  # 正しい名前が存在する場合
        print(f"✅ Using table: {table_name}")
    elif "sensro_data" in tables:
        table_name = "sensro_data"  # タイポ版が存在する場合
        print(f"✅ Using table: {table_name}")
    else:
        print(f"⚠️ Available tables: {tables}")
        # フォールバックとして最初のテーブルを使用
        if tables:
            table_name = tables[0]
            print(f"📍 Fallback to: {table_name}")
    
    # 利用可能なセンサー場所を取得
    try:
        cursor.execute(f"SELECT DISTINCT sensor_location FROM {table_name} WHERE sensor_location IS NOT NULL ORDER BY sensor_location")
        locations = [row[0] for row in cursor.fetchall()]
        if not locations:
            locations = ["default"]  # フォールバック
    except sqlite3.OperationalError:
        # sensor_locationカラムが存在しない場合
        locations = ["default"]
    
    # センサー場所によるフィルター条件を追加
    location_condition = ""
    if location_param != "all" and location_param in locations:
        location_condition = f" AND sensor_location = '{location_param}'"
    
    # 現在選択中のセンサー場所情報を設定
    current_location = "全ての場所"
    if location_param != "all" and location_param in locations:
        current_location = location_param
    
    # 集計方法による SQL クエリの変更
    if aggregate_param == "raw":
        cursor.execute(f'''
            SELECT timestamp, temperature, humidity, soil_moisture
            FROM {table_name}
            WHERE timestamp >= {time_condition}{location_condition}
            ORDER BY timestamp ASC
        ''')
        rows = cursor.fetchall()
        
        # 高度な時間フォーマット処理
        data_count = len(rows)
        time_format_rule = get_optimal_time_format(range_param, aggregate_param, data_count, screen_width)
        
        timestamps = []
        for r in rows:
            timestamp_str = r[0]
            formatted_time = format_timestamp(timestamp_str, aggregate_param, range_param, data_count, screen_width)
            timestamps.append(formatted_time)
        
        temperatures = [r[1] for r in rows]
        humidities = [r[2] for r in rows]
        moistures = [r[3] for r in rows]
        
    elif aggregate_param == "hourly":
        cursor.execute(f'''
            SELECT 
                strftime('%Y-%m-%d %H:00:00', timestamp) as hour_timestamp,
                AVG(temperature) as avg_temp,
                AVG(humidity) as avg_humidity,
                AVG(soil_moisture) as avg_moisture
            FROM {table_name}
            WHERE timestamp >= {time_condition}{location_condition}
            GROUP BY strftime('%Y-%m-%d %H', timestamp)
            ORDER BY hour_timestamp ASC
        ''')
        rows = cursor.fetchall()
        
        data_count = len(rows)
        time_format_rule = get_optimal_time_format(range_param, aggregate_param, data_count, screen_width)
        
        timestamps = []
        for r in rows:
            timestamp_str = r[0]
            formatted_time = format_timestamp(timestamp_str, aggregate_param, range_param, data_count, screen_width)
            timestamps.append(formatted_time)
        
        temperatures = [round(r[1], 1) if r[1] else None for r in rows]
        humidities = [round(r[2], 1) if r[2] else None for r in rows]
        moistures = [round(r[3], 1) if r[3] else None for r in rows]
        
    elif aggregate_param == "daily":
        cursor.execute(f'''
            SELECT 
                strftime('%Y-%m-%d 00:00:00', timestamp) as day_timestamp,
                AVG(temperature) as avg_temp,
                AVG(humidity) as avg_humidity,
                AVG(soil_moisture) as avg_moisture
            FROM {table_name}
            WHERE timestamp >= {time_condition}{location_condition}
            GROUP BY strftime('%Y-%m-%d', timestamp)
            ORDER BY day_timestamp ASC
        ''')
        rows = cursor.fetchall()
        
        data_count = len(rows)
        time_format_rule = get_optimal_time_format(range_param, aggregate_param, data_count, screen_width)
        
        timestamps = []
        for r in rows:
            timestamp_str = r[0]
            formatted_time = format_timestamp(timestamp_str, aggregate_param, range_param, data_count, screen_width)
            timestamps.append(formatted_time)
        
        temperatures = [round(r[1], 1) if r[1] else None for r in rows]
        humidities = [round(r[2], 1) if r[2] else None for r in rows]
        moistures = [round(r[3], 1) if r[3] else None for r in rows]
    
    # 統計情報の計算
    cursor.execute(f'''
        SELECT 
            COUNT(*) as count,
            AVG(temperature) as avg_temp,
            MIN(temperature) as min_temp,
            MAX(temperature) as max_temp,
            AVG(humidity) as avg_humidity,
            MIN(humidity) as min_humidity,
            MAX(humidity) as max_humidity,
            AVG(soil_moisture) as avg_moisture,
            MIN(soil_moisture) as min_moisture,
            MAX(soil_moisture) as max_moisture
        FROM {table_name}
        WHERE timestamp >= {time_condition}{location_condition}
    ''')
    
    stats = cursor.fetchone()
    conn.close()
    
    # 統計データの整理（None対応）
    if stats and stats[0] > 0:  # データが存在する場合
        statistics = {
            'count': stats[0],
            'temperature': {
                'avg': round(stats[1], 1) if stats[1] is not None else 0,
                'min': round(stats[2], 1) if stats[2] is not None else 0,
                'max': round(stats[3], 1) if stats[3] is not None else 0
            },
            'humidity': {
                'avg': round(stats[4], 1) if stats[4] is not None else 0,
                'min': round(stats[5], 1) if stats[5] is not None else 0,
                'max': round(stats[6], 1) if stats[6] is not None else 0
            },
            'soil_moisture': {
                'avg': round(stats[7], 1) if stats[7] is not None else 0,
                'min': round(stats[8], 1) if stats[8] is not None else 0,
                'max': round(stats[9], 1) if stats[9] is not None else 0
            }
        }
    else:  # データが存在しない場合
        statistics = {
            'count': 0,
            'temperature': {'avg': 0, 'min': 0, 'max': 0},
            'humidity': {'avg': 0, 'min': 0, 'max': 0},
            'soil_moisture': {'avg': 0, 'min': 0, 'max': 0}
        }
    
    return template('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>植物管理ダッシュボード</title>
            
            <!-- ファビコン設定 -->
            <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text x=%2250%%22 y=%2250%%22 style=%22dominant-baseline:central;text-anchor:middle;font-size:90px;%22>🌱</text></svg>">

            <!-- メタタグ -->
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta name="description" content="植物センサー監視ダッシュボード - 温度・湿度・土壌湿度をリアルタイム監視">
            <meta name="theme-color" content="#27ae60">
            
            <!-- Chart.js -->
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            
            <style>
                :root {
                    --primary-green: #27ae60;
                    --light-green: #2ecc71;
                    --dark-green: #1e8449;
                    --accent-blue: #3498db;
                    --accent-red: #e74c3c;
                    --bg-light: #f8f9fa;
                    --bg-white: #ffffff;
                    --text-dark: #2c3e50;
                    --text-gray: #7f8c8d;
                    --border-light: #ecf0f1;
                    --shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                
                body { 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 0;
                    background: linear-gradient(135deg, var(--bg-light) 0%, #e8f5e8 100%);
                    color: var(--text-dark);
                    line-height: 1.6;
                }
                
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }
                
                .header {
                    background: linear-gradient(135deg, var(--primary-green) 0%, var(--light-green) 100%);
                    color: white;
                    padding: 2rem;
                    border-radius: 15px;
                    margin-bottom: 2rem;
                    box-shadow: var(--shadow);
                    text-align: center;
                }
                
                .header h1 {
                    font-size: 2.5rem;
                    margin-bottom: 0.5rem;
                    font-weight: 300;
                }
                
                .header p {
                    font-size: 1.1rem;
                    opacity: 0.9;
                    margin-bottom: 0.5rem;
                }
                
                .sensor-location {
                    font-size: 1rem;
                    opacity: 0.95;
                    margin-top: 1rem;
                    padding: 0.5rem 1rem;
                    background: rgba(255, 255, 255, 0.2);
                    border-radius: 8px;
                    border-left: 4px solid rgba(255, 255, 255, 0.6);
                }
                
                .controls { 
                    background: var(--bg-white);
                    padding: 1.5rem;
                    border-radius: 12px;
                    margin-bottom: 1.5rem;
                    box-shadow: var(--shadow);
                    display: flex;
                    flex-wrap: wrap;
                    gap: 1rem;
                    align-items: center;
                }
                
                .controls form { 
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                }
                
                .controls label {
                    font-weight: 600;
                    color: var(--text-dark);
                }
                
                .controls select { 
                    padding: 0.5rem 1rem;
                    border-radius: 8px;
                    border: 2px solid var(--border-light);
                    background: white;
                    font-size: 0.95rem;
                    transition: all 0.2s ease;
                }
                
                .controls select:focus {
                    outline: none;
                    border-color: var(--primary-green);
                    box-shadow: 0 0 0 3px rgba(39, 174, 96, 0.1);
                }
                
                .stats { 
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 1.5rem;
                    margin: 1.5rem 0;
                }
                
                .stat-card { 
                    background: var(--bg-white);
                    border: none;
                    border-radius: 12px;
                    padding: 1.5rem;
                    box-shadow: var(--shadow);
                    transition: transform 0.2s ease, box-shadow 0.2s ease;
                    text-align: center;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                }

                .stat-card:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 8px rgba(0,0,0,0.15);
                }

                .stat-title { 
                    font-weight: 600;
                    margin-bottom: 0.5rem;
                    font-size: 1.1rem;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 0.5rem;
                }

                .stat-value { 
                    font-size: 2rem;
                    margin: 0.3rem 0;
                    font-weight: 700;
                    text-align: center;
                }

                .stat-range {
                    font-size: 0.9rem;
                    color: var(--text-gray);
                    text-align: center;
                    margin: 0;
                }
                
                .temp { color: var(--accent-red); }
                .humidity { color: var(--accent-blue); }
                .moisture { color: var(--primary-green); }
                
                .chart-container {
                    background: var(--bg-white);
                    padding: 1.5rem;
                    border-radius: 12px;
                    box-shadow: var(--shadow);
                    margin: 1.5rem 0;
                }
                
                .update-info { 
                    margin: 1rem 0;
                    color: var(--text-gray);
                    font-size: 0.9rem;
                    background: var(--border-light);
                    padding: 1rem;
                    border-radius: 8px;
                    border-left: 4px solid var(--primary-green);
                }
                
                .time-format-info {
                    margin: 0.5rem 0;
                    padding: 0.5rem;
                    background: rgba(39, 174, 96, 0.1);
                    border-radius: 6px;
                    font-size: 0.85rem;
                    color: var(--dark-green);
                }
                
                canvas { 
                    max-height: 400px;
                }
                
                /* レスポンシブ対応 */
                @media (max-width: 768px) {
                    .container {
                        padding: 1rem;
                    }
                    
                    .header h1 {
                        font-size: 2rem;
                    }
                    
                    .controls {
                        flex-direction: column;
                        align-items: stretch;
                    }
                    
                    .controls form {
                        justify-content: space-between;
                    }
                    
                    .stats {
                        grid-template-columns: 1fr;
                    }
                }
                
                /* ダークモード対応 */
                @media (prefers-color-scheme: dark) {
                    :root {
                        --bg-light: #1a1a1a;
                        --bg-white: #2d2d2d;
                        --text-dark: #f0f0f0;
                        --text-gray: #b0b0b0;
                        --border-light: #404040;
                    }
                    
                    body {
                        background: linear-gradient(135deg, var(--bg-light) 0%, #0f2a0f 100%);
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🌱 植物管理ダッシュボード</h1>
                    <p>IoTセンサーによるリアルタイム環境監視システム</p>
                    <div class="sensor-location">
                        📍 現在表示中: <strong>{{current_location}}</strong>
                    </div>
                </div>
                
                <div class="controls">
                    <form method="get" id="rangeForm">
                        <input type="hidden" name="aggregate" value="{{aggregate_param}}">
                        <input type="hidden" name="location" value="{{location_param}}">
                        <input type="hidden" name="width" id="screenWidth" value="{{screen_width}}">
                        <label for="range">📅 表示期間:</label>
                        <select name="range" onchange="updateWithScreenWidth(this.form)">
                            <option value="1h" {{'selected' if range_param=='1h' else ''}}>過去1時間</option>
                            <option value="6h" {{'selected' if range_param=='6h' else ''}}>過去6時間</option>
                            <option value="12h" {{'selected' if range_param=='12h' else ''}}>過去12時間</option>
                            <option value="24h" {{'selected' if range_param=='24h' else ''}}>過去24時間</option>
                            <option value="3d" {{'selected' if range_param=='3d' else ''}}>過去3日間</option>
                            <option value="7d" {{'selected' if range_param=='7d' else ''}}>過去7日間</option>
                            <option value="30d" {{'selected' if range_param=='30d' else ''}}>過去30日間</option>
                        </select>
                    </form>
                    
                    <form method="get" id="aggregateForm">
                        <input type="hidden" name="range" value="{{range_param}}">
                        <input type="hidden" name="location" value="{{location_param}}">
                        <input type="hidden" name="width" id="screenWidth2" value="{{screen_width}}">
                        <label for="aggregate">📊 集計方法:</label>
                        <select name="aggregate" onchange="updateWithScreenWidth(this.form)">
                            <option value="raw" {{'selected' if aggregate_param=='raw' else ''}}>生データ</option>
                            <option value="hourly" {{'selected' if aggregate_param=='hourly' else ''}}>1時間平均</option>
                            <option value="daily" {{'selected' if aggregate_param=='daily' else ''}}>1日平均</option>
                        </select>
                    </form>
                    
                    <form method="get" id="locationForm">
                        <input type="hidden" name="range" value="{{range_param}}">
                        <input type="hidden" name="aggregate" value="{{aggregate_param}}">
                        <input type="hidden" name="width" id="screenWidth3" value="{{screen_width}}">
                        <label for="location">📍 センサー場所:</label>
                        <select name="location" onchange="updateWithScreenWidth(this.form)">
                            <option value="all" {{'selected' if location_param=='all' else ''}}>全ての場所</option>
                            % for loc in locations:
                                <option value="{{loc}}" {{'selected' if location_param==loc else ''}}>{{loc}}</option>
                            % end
                        </select>
                    </form>
                </div>
                
                <div class="update-info">
                    📈 データ数: {{statistics['count']}}件 | 
                    集計方法: {{'生データ' if aggregate_param=='raw' else '1時間平均' if aggregate_param=='hourly' else '1日平均'}} |
                    最終更新: {{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}} |
                    📍 場所: {{current_location}}
                    
                    <div class="time-format-info">
                        ⏰ 時間表示: {{range_param}}期間の{{aggregate_param}}データに最適化 | 
                        データ点数: {{len(timestamps)}}点 | 
                        画面幅: {{screen_width}}px
                    </div>
                </div>
                
                <!-- 統計カード -->
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-title temp">🌡️ 温度 (℃)</div>
                        <div class="stat-value temp">{{statistics['temperature']['avg']}}</div>
                        <div class="stat-range">範囲: {{statistics['temperature']['min']}} ~ {{statistics['temperature']['max']}}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-title humidity">💧 湿度 (%)</div>
                        <div class="stat-value humidity">{{statistics['humidity']['avg']}}</div>
                        <div class="stat-range">範囲: {{statistics['humidity']['min']}} ~ {{statistics['humidity']['max']}}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-title moisture">🌱 土壌湿度 (%)</div>
                        <div class="stat-value moisture">{{statistics['soil_moisture']['avg']}}</div>
                        <div class="stat-range">範囲: {{statistics['soil_moisture']['min']}} ~ {{statistics['soil_moisture']['max']}}</div>
                    </div>
                </div>
                
                <!-- グラフ -->
                <div class="chart-container">
                    <canvas id="chart"></canvas>
                </div>
            </div>
            
            <script>
                // 画面幅の検出と送信
                function updateWithScreenWidth(form) {
                    const screenWidth = window.innerWidth;
                    const widthInput = form.querySelector('input[name="width"]');
                    if (widthInput) {
                        widthInput.value = screenWidth;
                    }
                    form.submit();
                }
                
                // 初期ロード時に画面幅を設定
                window.addEventListener('load', function() {
                    document.getElementById('screenWidth').value = window.innerWidth;
                    document.getElementById('screenWidth2').value = window.innerWidth;
                    document.getElementById('screenWidth3').value = window.innerWidth;
                });
                
                // 画面リサイズ時の対応
                let resizeTimer;
                window.addEventListener('resize', function() {
                    clearTimeout(resizeTimer);
                    resizeTimer = setTimeout(function() {
                        const currentWidth = window.innerWidth;
                        const storedWidth = parseInt(document.getElementById('screenWidth').value);
                        
                        // 大幅な画面サイズ変更時にリロード
                        if (Math.abs(currentWidth - storedWidth) > 200) {
                            const url = new URL(window.location.href);
                            url.searchParams.set('width', currentWidth);
                            window.location.href = url.toString();
                        }
                    }, 500);
                });
                
                // 動的な最大ティック数計算
                function getMaxTicks() {
                    const width = window.innerWidth;
                    const dataCount = {{len(timestamps)}};
                    
                    if (width < 600) return Math.min(6, dataCount);
                    if (width < 900) return Math.min(10, dataCount);
                    if (width < 1200) return Math.min(15, dataCount);
                    return Math.min(20, dataCount);
                }
                
                const ctx = document.getElementById('chart').getContext('2d');
                const chart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: {{!json.dumps(timestamps)}},
                        datasets: [
                            {
                                label: '🌡️ 温度 (℃)',
                                data: {{!json.dumps(temperatures)}},
                                borderColor: '#e74c3c',
                                backgroundColor: 'rgba(231, 76, 60, 0.1)',
                                fill: false,
                                tension: 0.3,
                                pointRadius: window.innerWidth < 768 ? 2 : 3,
                                pointHoverRadius: window.innerWidth < 768 ? 4 : 6
                            },
                            {
                                label: '💧 湿度 (%)',
                                data: {{!json.dumps(humidities)}},
                                borderColor: '#3498db',
                                backgroundColor: 'rgba(52, 152, 219, 0.1)',
                                fill: false,
                                tension: 0.3,
                                pointRadius: window.innerWidth < 768 ? 2 : 3,
                                pointHoverRadius: window.innerWidth < 768 ? 4 : 6
                            },
                            {
                                label: '🌱 土壌湿度 (%)',
                                data: {{!json.dumps(moistures)}},
                                borderColor: '#27ae60',
                                backgroundColor: 'rgba(39, 174, 96, 0.1)',
                                fill: false,
                                tension: 0.3,
                                pointRadius: window.innerWidth < 768 ? 2 : 3,
                                pointHoverRadius: window.innerWidth < 768 ? 4 : 6,
                                pointBackgroundColor: function(context) {
                                    const value = context.parsed.y;
                                    return value < 30 ? '#e74c3c' : '#27ae60';
                                }
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            intersect: false,
                            mode: 'index'
                        },
                        plugins: {
                            legend: {
                                position: 'top',
                                labels: {
                                    usePointStyle: true,
                                    padding: window.innerWidth < 768 ? 10 : 20,
                                    font: {
                                        size: window.innerWidth < 768 ? 10 : 12
                                    }
                                }
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0,0,0,0.8)',
                                titleColor: 'white',
                                bodyColor: 'white',
                                borderColor: '#27ae60',
                                borderWidth: 1,
                                titleFont: {
                                    size: window.innerWidth < 768 ? 11 : 13
                                },
                                bodyFont: {
                                    size: window.innerWidth < 768 ? 10 : 12
                                },
                                callbacks: {
                                    afterLabel: function(context) {
                                        if (context.datasetIndex === 2 && context.parsed.y < 30) {
                                            return '⚠️ 水やりが必要です';
                                        }
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                title: {
                                    display: true,
                                    text: '📅 時間',
                                    font: {
                                        size: window.innerWidth < 768 ? 12 : 14,
                                        weight: 'bold'
                                    }
                                },
                                ticks: {
                                    maxRotation: window.innerWidth < 768 ? 60 : 45,
                                    minRotation: window.innerWidth < 768 ? 45 : 0,
                                    maxTicksLimit: getMaxTicks(),
                                    font: {
                                        size: window.innerWidth < 768 ? 9 : 11
                                    },
                                    callback: function(value, index, values) {
                                        const label = this.getLabelForValue(value);
                                        
                                        // モバイルでは更に簡略化
                                        if (window.innerWidth < 768) {
                                            if (label.includes(' ')) {
                                                const parts = label.split(' ');
                                                if (parts.length >= 2) {
                                                    // "06-18 13:30" → "13:30"
                                                    return parts[1];
                                                }
                                            }
                                        }
                                        
                                        return label;
                                    }
                                },
                                grid: {
                                    display: true,
                                    color: 'rgba(0,0,0,0.1)'
                                }
                            },
                            y: {
                                title: {
                                    display: true,
                                    text: '📊 値',
                                    font: {
                                        size: window.innerWidth < 768 ? 12 : 14,
                                        weight: 'bold'
                                    }
                                },
                                ticks: {
                                    font: {
                                        size: window.innerWidth < 768 ? 9 : 11
                                    }
                                },
                                beginAtZero: true,
                                max: 100,
                                grid: {
                                    display: true,
                                    color: 'rgba(0,0,0,0.1)'
                                }
                            }
                        },
                        elements: {
                            point: {
                                radius: window.innerWidth < 768 ? 2 : 3,
                                hoverRadius: window.innerWidth < 768 ? 4 : 6,
                                borderWidth: 2
                            },
                            line: {
                                borderWidth: window.innerWidth < 768 ? 2 : 3
                            }
                        }
                    }
                });
                
                // グラフのサイズ調整
                chart.canvas.parentNode.style.height = window.innerWidth < 768 ? '300px' : '400px';
                
                // 自動更新機能（30秒ごと）- 画面幅情報を含める
                setInterval(function() {
                    const url = new URL(window.location.href);
                    url.searchParams.set('width', window.innerWidth);
                    window.location.href = url.toString();
                }, 30000);
                
                // ページタイトルにリアルタイム情報を追加
                function updateTitle() {
                    const now = new Date();
                    const time = now.toLocaleTimeString('ja-JP');
                    const rangeText = {
                        '1h': '1H',
                        '6h': '6H', 
                        '12h': '12H',
                        '24h': '24H',
                        '3d': '3D',
                        '7d': '7D',
                        '30d': '30D'
                    };
                    const aggregateText = {
                        'raw': 'RAW',
                        'hourly': 'H-AVG',
                        'daily': 'D-AVG'
                    };
                    
                    document.title = `植物管理 - ${rangeText['{{range_param}}']} ${aggregateText['{{aggregate_param}}']} - ${time}`;
                }
                
                updateTitle();
                setInterval(updateTitle, 1000);
                
                // パフォーマンス情報の表示
                console.log('📊 Dashboard Performance Info:');
                console.log(`- Data points: {{len(timestamps)}}`);
                console.log(`- Screen width: ${window.innerWidth}px`);
                console.log(`- Max ticks: ${getMaxTicks()}`);
                console.log(`- Range: {{range_param}}`);
                console.log(`- Aggregate: {{aggregate_param}}`);
                console.log(`- Location: {{location_param}}`);
                console.log(`- Mobile mode: ${window.innerWidth < 768}`);
            </script>
        </body>
        </html>
    ''', 
    timestamps=timestamps, 
    temperatures=temperatures, 
    humidities=humidities, 
    moistures=moistures, 
    range_param=range_param,
    aggregate_param=aggregate_param,
    location_param=location_param,
    statistics=statistics,
    current_location=current_location,
    locations=locations,
    screen_width=screen_width,
    time_format_rule=time_format_rule,
    len=len,
    json=json,
    datetime=datetime)

@route('/api/data')
def api_data():
    """API endpoint for raw data access with advanced formatting"""
    range_param = request.query.range or "24h"
    aggregate_param = request.query.aggregate or "raw"
    location_param = request.query.location or "all"
    screen_width = int(request.query.width or "1200")
    
    time_conditions = {
        "1h": "datetime('now', '-1 hours')",
        "6h": "datetime('now', '-6 hours')",
        "12h": "datetime('now', '-12 hours')",
        "24h": "datetime('now', '-1 days')",
        "3d": "datetime('now', '-3 days')",
        "7d": "datetime('now', '-7 days')",
        "30d": "datetime('now', '-30 days')"
    }
    
    time_condition = time_conditions.get(range_param, time_conditions["24h"])
    
    conn = sqlite3.connect("sensor_data.db")
    cursor = conn.cursor()
    
    # テーブル名を確認して適切なものを使用
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    table_name = "sensor_data"
    if "sensor_data" in tables:
        table_name = "sensor_data"
    elif "sensro_data" in tables:
        table_name = "sensro_data"
    
    # センサー場所によるフィルター条件を追加
    location_condition = ""
    if location_param != "all":
        location_condition = f" AND sensor_location = '{location_param}'"
    
    cursor.execute(f'''
        SELECT timestamp, temperature, humidity, soil_moisture
        FROM {table_name}
        WHERE timestamp >= {time_condition}{location_condition}
        ORDER BY timestamp ASC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    # 高度な時間フォーマット適用
    data_count = len(rows)
    formatted_timestamps = []
    
    for r in rows:
        formatted_time = format_timestamp(r[0], aggregate_param, range_param, data_count, screen_width)
        formatted_timestamps.append(formatted_time)
    
    data = {
        "timestamps": formatted_timestamps,
        "raw_timestamps": [r[0] for r in rows],
        "temperatures": [r[1] for r in rows],
        "humidities": [r[2] for r in rows],
        "moistures": [r[3] for r in rows],
        "metadata": {
            "range": range_param,
            "aggregate": aggregate_param,
            "location": location_param,
            "data_count": data_count,
            "screen_width": screen_width,
            "format_info": get_optimal_time_format(range_param, aggregate_param, data_count, screen_width)
        }
    }
    
    response.content_type = 'application/json'
    return json.dumps(data, ensure_ascii=False, indent=2)

@route('/api/format-test')
def format_test():
    """時間フォーマットのテスト用エンドポイント"""
    test_timestamp = "2025-06-18 13:33:49.265477"
    
    test_results = {}
    
    for range_param in ["1h", "6h", "12h", "24h", "3d", "7d", "30d"]:
        for aggregate_param in ["raw", "hourly", "daily"]:
            for screen_width in [375, 768, 1024, 1200, 1920]:
                key = f"{range_param}_{aggregate_param}_{screen_width}px"
                test_results[key] = {
                    "formatted": format_timestamp(test_timestamp, aggregate_param, range_param, 50, screen_width),
                    "rule": get_optimal_time_format(range_param, aggregate_param, 50, screen_width)
                }
    
    response.content_type = 'application/json'
    return json.dumps(test_results, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    print("🌱 高度な時間表示対応植物管理ダッシュボード起動中...")
    print("🌐 URL: http://0.0.0.0:8080")
    print("🔧 API endpoints:")
    print("   - /api/data - 高度フォーマット済みデータ")
    print("   - /api/format-test - 時間フォーマットテスト")
    print("⏰ 動的時間表示機能:")
    print("   ✅ 集計方法別最適化")
    print("   ✅ 表示期間別調整") 
    print("   ✅ 画面幅レスポンシブ")
    print("   ✅ データ点数適応")
    print("   ✅ センサー場所選択")
    run(host='0.0.0.0', port=8080, debug=True)