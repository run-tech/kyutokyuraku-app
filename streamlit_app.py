import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
from datetime import datetime, time
import pytz
from io import StringIO
import pandas as pd
import pickle

CACHE_FILE = "19RT1ZT3nLrFLWi7BO89lV_URauXbfIxo" # cache_local_data.pkl
LOG_FILE = "1oMK080Fx5CjvlD918p-eWwfAWQ8HMPKj" # kyutokyuraku.log

# =========================================================
# 指定したGoogleDocumentのファイルをダウンロード
# =========================================================
def get_gd_data(file_id):
    url = f"https://drive.google.com/uc?id={file_id}&export=download"
    # データを返却
    return requests.get(url)
    
# =========================================================
# ログファイル取得
# =========================================================
def get_log_file(file_id):
    response = get_gd_data(file_id)
    
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
        
        # 時間の整形(文字列から HH:MM:SS を抽出)
        df['raw_time'] = pd.to_datetime(df['time'].str.strip('[]')).dt.time
        df['display_time'] = df['raw_time'].apply(lambda x: x.strftime('%H:%M:%S'))
        
        return df, last_updated
    else:
        raise Exception(f"ファイルの取得に失敗しました。ステータスコード: {response.status_code}")

# =========================================================
# GoogleDocumentからキャッシュファイル取得
# =========================================================
def get_cache_file(file_id):
    response = get_gd_data(file_id)
    
    if response.status_code == 200:
        # pickle.loads でバイナリデータを辞書に変換
        data = pickle.loads(response.content)
        
        # 銘柄コードを抽出
        codes = []
        for i in range(1, 201):
            code = data.get(i, {}).get("code", "")
            # 空文字でない、かつ初期値やダミーでないものを追加
            if code and code != "":
                codes.append(code)
        return codes
    else:
        return []

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
# 初期設定
# =========================================================
# --- セッション状態の初期化 ---
if "filter_query" not in st.session_state:
    st.session_state.filter_query = ""
if "last_df" not in st.session_state:
    # 最初の読み込みで失敗してもエラーにならないよう空のDataFrameを作っておく
    st.session_state.last_df = pd.DataFrame(columns=['id', 'time', 'message'])

# =========================================================
# サイドバーの設定
# =========================================================
with st.sidebar:
    st.header("⚙️ 設定")
    # 自動更新のON/OFF
    auto_refresh_enabled = st.checkbox("自動更新を有効にする", value=False)
    
    with st.form(key='search_form'):
        st.header("🔍 絞り込み条件")
        # text_inputの値を直接使わず、一度変数に受ける
        search_query = st.text_input("キーワード入力", placeholder="銘柄コード、銘柄名など", value=st.session_state.filter_query)

        # 時間指定
        time_options = [time(h, m) for h in range(8, 17) for m in [0, 15, 30, 45] if not (h==16 and m>0)]
        start_time = st.sidebar.selectbox(
            "表示開始時刻", 
            options=time_options, 
            index=4, # 9:00をデフォルトにする場合
            format_func=lambda x: x.strftime("%H:%M")
        )
        # 表示件数
        limit_count = st.number_input("表示件数（各カテゴリ）", min_value=10, max_value=5000, value=500, step=100)

        # フォーム確定用のボタン（これが押されるまで反映されない）
        submit_button = st.form_submit_button(label='条件を適用して検索')
    
# =========================================================
# 画面設定
# =========================================================
# --- タイトル ---
st.title(":chart: 株価情報モニタ（仮）")

# --- 変数 ---
reload_interval = 60000 # 60秒(60000ミリ秒)

# --- 指定した時間ごとに自動更新する設定 ---
# keyは任意の文字列でOK
if auto_refresh_enabled:
    # チェックボックスがONの時だけ実行
    st_autorefresh(interval=reload_interval, key="datarefresh")

# --- データ取得・表示処理 ---
try:
    df, last_updated = get_log_file(LOG_FILE)
    codes = get_cache_file(CACHE_FILE)

    st.write(f"最終更新: {last_updated} ／ 全 {len(df):,} 行")
    st.write(f"※自動更新をオンにすると{int(reload_interval / 1000)}秒ごとに再読み込みします")
    
    # --- フィルタリング処理 ---
    # 1. 時間で絞り込み
    filtered_df = df[df['raw_time'] >= start_time]
    
    # 2. キーワードで絞り込み
    if search_query:
        filtered_df = filtered_df[filtered_df['message'].str.contains(search_query, case=False, na=False)]

    # --- カテゴリ別表示 ---
    id_map = {1: "🔥 急騰急落", 2: "📈 傾向", 3: "📊 テクニカル", 9: "⚙️ システム"}
    
    for target_id, label in id_map.items():
        # IDで絞り込み、最新順にする
        cat_df = filtered_df[filtered_df['id'] == target_id].iloc[::-1]
        
        # 3. 表示件数を制限（ここで高速化）
        display_df = cat_df.head(limit_count)
        
        st.subheader(f"{label} (最新 {len(display_df)} 件)")
        
        if display_df.empty:
            st.caption("該当データなし")
            continue

        with st.container(height=250):
            # 文字列結合して一気に表示するとさらに速いですが、
            # 個別にマークダウンで出す場合は head() で件数を絞るのが最も効きます
            for _, row in display_df.iterrows():
                st.markdown(f"`{row['display_time']}` : {row['message']}")

    st.divider()  # 区切り線


    st.header("📊 監視銘柄")
    st.write(", ".join(map(str, codes)) if codes else "監視中の銘柄はありません。")    
    st.caption(f"合計: {len(codes)} 銘柄")

except Exception as e:
    st.error(f"データ読み込みエラー: {e}")
