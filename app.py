import json
import os
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

# 1. 初始化 Gemini 與共用計分板（活動期間所有連線手機共享同一份分數）
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

@st.cache_resource
def get_scoreboard():
    return {"Team 1": 0, "Team 2": 0, "Team 3": 0, "Team 4": 0, "Team 5": 0}

scores = get_scoreboard()

# 2. 網頁標題與即時排行榜
st.set_page_config(page_title="Xiangshan Crab Blitz", page_icon="🦀")
st.title("🦀 香山濕地蟹蟹大搜查")
st.caption("Hallo Krabben! Upload your crab photo for AI judging.")

st.subheader("🏆 即時排行榜 Live Scoreboard")
st.bar_chart(scores)

# 3. 學生上傳區
team = st.selectbox("選擇組別 Select Your Team", list(scores.keys()))
uploaded_file = st.file_uploader(
    "拍照或從相簿上傳（建議先用手機原生相機拉近拍好再上傳）",
    type=["jpg", "jpeg", "png"]
)

# 4. AI 裁判辨識邏輯
if uploaded_file and st.button("🚀 提交給 AI 裁判評分 (Submit)"):
    img = Image.open(uploaded_file)
    st.image(img, caption="已上傳照片", use_container_width=True)

    prompt = """
    你是新竹香山濕地生態競賽的雙語 AI 裁判。請分析這張照片並嚴格以 JSON 格式回傳結果：
    目標物種與分數：
    - 弧邊招潮蟹 (Fiddler Crab - Tubuca arcuata): 1 分
    - 清白招潮蟹 (Milky Fiddler Crab): 1 分
    - 短指和尚蟹 (Soldier Crab): 2 分
    - 萬歲大眼蟹 (Sentinel Crab): 2 分
    - 台灣招潮蟹 (Taiwanese Fiddler Crab): 4 分
    - 彈塗魚 (Mudskipper): 2 分
    - 其他或模糊無法辨識: 0 分

    請同時檢查畫面角落是否有「人類手勢或號碼牌」（防作弊機制）。
    回傳 JSON 格式（不要加 markdown 標記）：
    {
      "species": "物種中英文名稱",
      "has_hand_sign": true 或 false,
      "points": 數字(若無手勢或無法辨識則給 0),
      "feedback": "給學生的簡短中英文評語（說明辨識特徵或未得分原因）"
    }
    """

    with st.spinner("AI 裁判鑑定中... Judging..."):
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[img, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        result = json.loads(response.text)

    # 5. 顯示判決結果並加分
    if result["points"] > 0:
        scores[team] += result["points"]
        st.success(f"🎉 辨識成功！{result['species']}（+{result['points']} 分）")
        st.balloons()
    else:
        st.warning(f"😅 本次未得分：{result['species']}")

    st.info(f"🤖 AI 評語：{result['feedback']}")
