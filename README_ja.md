# 🌱 植物IoTダッシュボード

*他の言語で読む: [English](README.md)*

Raspberry Piと環境センサーを使用したリアルタイム植物健康監視システム。Webベースのダッシュボード付き。

![ダッシュボードスクリーンショット](docs/screenshots/dashboard-desktop.png)

## ✨ 機能

- **🌡️ 環境モニタリング**: 温度、湿度、土壌水分の追跡
- **📊 インタラクティブダッシュボード**: Chart.jsによるリアルタイムデータ可視化
- **📱 レスポンシブデザイン**: モバイルフレンドリーなインターフェース
- **📧 スマートアラート**: 土壌水分低下時のメール通知
- **🔄 自動更新**: 30秒間隔での更新
- **📍 複数地点対応**: 複数のセンサー地点の追跡
- **⏰ 柔軟な時間範囲**: 1時間から30日間のデータ表示
- **📈 データ集約**: 生データ、時間平均、日平均

## 🛠️ 必要なハードウェア

- Raspberry Pi（3B+以降）
- DHT11 温度・湿度センサー
- SEN0193 土壌水分センサー
- MCP3008 ADC（土壌センサー用）
- ブレッドボードとジャンパーワイヤー

## 🔌 配線図

```
DHT11:
- VCC → 3.3V
- Data → GPIO 14
- GND → GND

MCP3008（土壌センサー用）:
- VDD → 3.3V
- VREF → 3.3V
- AGND → GND
- DGND → GND
- CLK → GPIO 11 (SCLK)
- DOUT → GPIO 9 (MISO)
- DIN → GPIO 10 (MOSI)
- CS → GPIO 8 (CE0)

SEN0193 土壌センサー:
- VCC → 5V
- Signal → MCP3008 CH0
- GND → GND
```

## 🚀 インストール

### 1. リポジトリをクローン
```bash
git clone https://github.com/yourusername/plant-iot-dashboard.git
cd plant-iot-dashboard
```

### 2. 依存関係をインストール
```bash
pip3 install -r requirements.txt
```

### 3. SPIインターフェースを有効化
```bash
sudo raspi-config
# Interface Options → SPI → Enable
```

### 4. 環境設定
```bash
cp .env.example .env
nano .env
# Gmailの認証情報を編集
```

### 5. データベースの初期化
```bash
python3 log_sensor_data.py
```

### 6. Cronジョブの設定
```bash
crontab -e
# 以下の行を追加:
*/10 * * * * cd /home/aiot/plant-iot-dashboard && python3 log_sensor_data.py
```

### 7. ダッシュボードの起動
```bash
python3 dashboard.py
```

ブラウザで `http://your-pi-ip:8080` にアクセスしてください。

## 📊 使用方法

### ダッシュボードの操作

- **📅 時間範囲**: 1時間から30日間を選択
- **📈 集約**: 生データ、時間平均、または日平均
- **📍 地点**: センサー地点でフィルタリング

### データエクスポート

API経由で生データにアクセス:
```
GET /api/data?range=24h&aggregate=raw&location=ohana_001
GET /api/format-test  # 時間フォーマットのテスト
```

## 📧 メールアラート

以下の場合に自動でアラートを送信:
- 土壌水分が30%を下回った時
- センサー読み取りエラー発生時
- システム例外発生時

## 🗂️ プロジェクト構成

```
plant-iot-dashboard/
├── dashboard.py          # Webダッシュボードサーバー
├── log_sensor_data.py    # センサーデータ収集
├── models.py            # データベースモデル
├── dht11.py            # DHT11センサードライバー
├── dht11_sample.py     # DHT11センサーテストプログラム
├── sen0193.py          # 土壌水分センサードライバー
├── sen0193_sample.py   # 土壌水分テストプログラム
├── requirements.txt     # Python依存関係
├── .env.example        # 環境設定テンプレート
└── logs/               # アプリケーションログ
```

## 🔧 設定

### センサー地点
`log_sensor_data.py`の`SENSOR_LOCATION`を編集:
```python
SENSOR_LOCATION = "ohana_001"  # センサー名
```

### アラート閾値
水分アラート閾値の変更:
```python
if soil_moisture < 30.0:  # 閾値をここで変更
    send_moisture_alert(soil_moisture, timestamp)
```

## 📈 データスキーマ

```sql
CREATE TABLE sensor_data (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    temperature REAL,
    humidity REAL,
    soil_moisture REAL,
    sensor_location TEXT
);
```

## 🐛 トラブルシューティング

### よくある問題

1. **GPIOアクセス拒否**:
   ```bash
   sudo usermod -a -G gpio $USER
   # ログアウト後、再ログイン
   ```

2. **SPIが有効でない**:
   ```bash
   sudo raspi-config
   # Interface Options → SPI → Enable
   ```

3. **データベースがロックされている**:
   ```bash
   sudo pkill -f python3.*log_sensor
   ```

4. **ポート8080が使用中**:
   ```bash
   sudo lsof -i :8080
   sudo kill -9 PID
   ```

## 📱 スクリーンショット

### デスクトップダッシュボード
![デスクトップ表示](docs/screenshots/dashboard-desktop.png)

### モバイルダッシュボード
![モバイル表示](docs/screenshots/dashboard-mobile.png)

### メールアラート例
![メールアラート](docs/screenshots/email-alert.png)

## 🤝 コントリビューション

1. リポジトリをフォーク
2. 機能ブランチの作成（`git checkout -b feature/amazing-feature`）
3. 変更をコミット（`git commit -m 'Add amazing feature'`）
4. ブランチにプッシュ（`git push origin feature/amazing-feature`）
5. プルリクエストを作成

## 📄 ライセンス

このプロジェクトはMITライセンスの下でライセンスされています。詳細は[LICENSE](LICENSE)ファイルをご覧ください。

## 🙏 謝辞

- [Bottle](https://bottlepy.org/) - 軽量なPython Webフレームワーク
- [Chart.js](https://www.chartjs.org/) - 美しいチャート
- [SQLAlchemy](https://www.sqlalchemy.org/) - データベースツールキット
- Raspberry Pi Foundation - 素晴らしいハードウェア

## 📞 サポート

ご質問や問題がある場合:
- [Issue](https://github.com/yourusername/plant-iot-dashboard/issues)を作成
- [ドキュメント](docs/)を確認
- メール: kinarita@gmail.com

---

**🌱 健康な植物と幸せなガーデナーのために作られました！**