import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
from datetime import datetime
import pytz
from io import StringIO
import pandas as pd

CASH_FILE = "19RT1ZT3nLrFLWi7BO89lV_URauXbfIxo" # cash_local_data.pkl
LOG_FILE = "1eJJ5CeH676xaBl8YMPZmEsb1-1tuwRdM" # kyutokyuraku.log

# =========================================================
# GoogleDocumentからファイル取得
# =========================================================
def get_gd_file(file_id):
    # 指定したGoogleDocumentのファイルをダウンロード
    url = f"https://drive.google.com/uc?id={file_id}&export=download"
    # データを取得
    response = requests.get(url)
    
    # レスポンスが正常か確認
    if response.status_code == 200:
        # HTTPヘッダーから日時を取得
        last_modified_str = response.headers.get('Last-Modified')
        
        if last_modified_str:
            # 文字列を日時に変換
            dt = datetime.strptime(last_modified_str, '%a, %d %b %Y %H:%M:%S %Z')
            # 日本時間に変換
            dt_jst = dt.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Asia/Tokyo'))
            last_updated = dt_jst.strftime('%Y/%m/%d %H:%M')
        else:
            # ヘッダーから取れない場合は、現在の取得時刻を表示するなどの代用
            last_updated = "日時取得不可（直近の読み込み時刻: " + datetime.now(pytz.timezone('Asia/Tokyo')).strftime('%Y/%m/%d %H:%M') + ")"
            
        # 文字コードが不明な場合は utf-8 や shift_jis を試してください
        csv_data = StringIO(response.text)
        df = pd.read_csv(csv_data, header=None, names=['id', 'time', 'message'])
        return df, last_updated
    else:
        raise Exception(f"ファイルの取得に失敗しました。ステータスコード: {response.status_code}")

# =========================================================
# スタイルシート（css）
# =========================================================
st.markdown("""
    <style>
    /* markdownの段落間の余白を削る */
    .stMarkdown p {
        margin-bottom: 0px;
        line-height: 1.2;
    }
    /* コンテナ内の要素間の隙間を調整 */
    [data-testid="stVerticalBlock"] > div {
        padding-top: 0px;
        padding-bottom: 2px;
    }
    </style>
    """, unsafe_allow_html=True)


# =========================================================
# GUI メイン画面
# =========================================================
# --- セッション状態の初期化 (ここを st.title の上に追加) ---
if "filter_query" not in st.session_state:
    st.session_state.filter_query = ""
if "last_df" not in st.session_state:
    # 最初の読み込みで失敗してもエラーにならないよう空のDataFrameを作っておく
    st.session_state.last_df = pd.DataFrame(columns=['id', 'time', 'message'])

st.title(":chart: 株価情報モニター（お試し）")

reload_interval = 60000 # 60秒(60000ミリ秒)

# --- 指定した時間ごとに自動更新する設定 ---
# keyは任意の文字列でOK
st_autorefresh(interval=reload_interval, key="datarefresh")

try:
    # データの読み込み
    # 自動更新が走るたびに、この get_gd_file が実行されて最新データが取得される
    new_df, last_updated = get_gd_file(LOG_FILE)

    # 時間の整形(文字列から HH:MM:SS を抽出)
    new_df['time'] = pd.to_datetime(new_df['time'].str.strip('[]')).dt.strftime('%H:%M:%S')
    
    # 取得成功時にデータをキャッシュに保存
    st.session_state.last_df = new_df
    st.write(f"読込ファイル最終更新時間: {last_updated}")
    st.write(f"※{reload_interval / 1000}秒ごとに再読み込みします ")

except Exception as e:
    # 取得失敗時は、前回のデータを使いつつ警告を表示
    st.warning(f"最新データの取得に失敗しました（前回のデータを表示中）: {e}")

df = st.session_state.last_df

with st.sidebar:
    st.header("🔍 表示フィルタ")
    # text_inputの値を直接使わず、一度変数に受ける
    input_val = st.text_input("キーワード入力（銘柄コードや銘柄名など）", placeholder="例: 6146", value=st.session_state.filter_query)
    
    if st.button("フィルタ適用"):
        st.session_state.filter_query = input_val
    
    if st.button("クリア"):
        st.session_state.filter_query = ""
        st.rerun()

current_filter = st.session_state.filter_query

if current_filter:
    display_df = df[df['message'].str.contains(current_filter, case=False, na=False)]
    st.info(f"「{current_filter}」で絞り込み中")
else:
    display_df = df.copy()

# IDと表示名のマッピング定義
id_map = {
    1: "🔥 急騰急落の情報",
    2: "📈 傾向の情報",
    3: "📊 テクニカル情報",
    9: "⚙️ システムログ"
}

# 3. 各IDごとに表示
for target_id, label in id_map.items():
    # IDで絞り込み、かつ最新を上にする (.iloc[::-1])
    filtered_df = display_df[display_df['id'] == target_id].iloc[::-1]
    
    st.subheader(label)
    
    # 該当データがない場合の表示
    if filtered_df.empty:
        st.caption("該当するデータはありません。")
        continue

    with st.container(height=250):
        for _, row in filtered_df.iterrows():
            st.markdown(f"`{row['time']}` : {row['message']}")
