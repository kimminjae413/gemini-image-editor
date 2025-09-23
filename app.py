import streamlit as st
import requests
from PIL import Image
import io
import time
from datetime import datetime
import uuid

# 페이지 설정
st.set_page_config(
    page_title="AI 헤어 스타일 변경 서비스",
    page_icon="💇‍♀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 스타일링
st.markdown("""
<style>
    .main-header {
        text-align: center;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .feature-box {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #667eea;
        margin: 1rem 0;
    }
    .success-box {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
    }
    .error-box {
        background: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #f5c6cb;
    }
</style>
""", unsafe_allow_html=True)

# API 설정
API_BASE = "http://localhost:8000"

# 세션 상태 초기화
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]

def check_api_connection():
    """API 서버 연결 확인"""
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def upload_seed_image(image_file, user_id):
    """시드 이미지 업로드"""
    try:
        files = {"seed_image": image_file.getvalue()}
        data = {"user_id": user_id}
        response = requests.post(f"{API_BASE}/upload-seed/", files=files, data=data)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"업로드 실패: {e}")
        return None

def get_user_seeds(user_id):
    """사용자 시드 목록 조회"""
    try:
        response = requests.get(f"{API_BASE}/seeds/{user_id}")
        return response.json() if response.status_code == 200 else {"seeds": []}
    except:
        return {"seeds": []}

def process_hair_transfer(seed_id, ref_image):
    """헤어 변경 처리"""
    try:
        files = {"reference_image": ref_image.getvalue()}
        data = {"seed_id": seed_id}
        response = requests.post(f"{API_BASE}/transfer-hair/", files=files, data=data)
        return response if response.status_code == 200 else None
    except Exception as e:
        st.error(f"처리 실패: {e}")
        return None

def get_processing_history(user_id):
    """처리 기록 조회"""
    try:
        response = requests.get(f"{API_BASE}/history/{user_id}")
        return response.json() if response.status_code == 200 else {"history": []}
    except:
        return {"history": []}

# 메인 UI
st.markdown("""
<div class="main-header">
    <h1>💇‍♀️ AI 헤어 스타일 변경 서비스</h1>
    <p>원하는 헤어스타일을 AI로 미리 체험해보세요!</p>
</div>
""", unsafe_allow_html=True)

# API 연결 상태 확인
if not check_api_connection():
    st.error("⚠️ API 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.")
    st.code("python main.py")
    st.stop()

# 사이드바
with st.sidebar:
    st.header("🎛️ 설정")
    
    # 사용자 ID 표시
    st.info(f"사용자 ID: {st.session_state.user_id}")
    
    if st.button("🔄 새 사용자 ID 생성"):
        st.session_state.user_id = str(uuid.uuid4())[:8]
        st.rerun()
    
    st.divider()
    
    # 기능 설명
    st.markdown("""
    <div class="feature-box">
        <h4>📋 사용 방법</h4>
        <ol>
            <li>시드 이미지 업로드</li>
            <li>원하는 헤어스타일 참조 이미지 선택</li>
            <li>AI 변환 실행</li>
            <li>결과 확인 및 다운로드</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)

# 메인 탭
tab1, tab2, tab3, tab4 = st.tabs(["🎨 헤어 변경", "📸 시드 업로드", "📝 처리 기록", "ℹ️ 정보"])

with tab2:
    st.header("📸 시드 이미지 업로드")
    st.markdown("얼굴이 명확히 보이는 정면 사진을 업로드해주세요.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        seed_file = st.file_uploader(
            "시드 이미지 선택", 
            type=['png', 'jpg', 'jpeg'],
            help="최대 10MB, PNG/JPEG 형식"
        )
        
        if seed_file:
            # 이미지 미리보기
            image = Image.open(seed_file)
            st.image(image, caption="미리보기", width=300)
            
            # 이미지 정보
            st.caption(f"파일명: {seed_file.name}")
            st.caption(f"크기: {image.size}")
            st.caption(f"용량: {len(seed_file.getvalue()) / 1024:.1f} KB")
    
    with col2:
        if seed_file and st.button("📤 업로드", type="primary"):
            with st.spinner("업로드 중..."):
                result = upload_seed_image(seed_file, st.session_state.user_id)
                
                if result:
                    st.markdown(f"""
                    <div class="success-box">
                        ✅ 업로드 완료!<br>
                        ID: {result['seed_id'][:8]}...
                    </div>
                    """, unsafe_allow_html=True)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.markdown("""
                    <div class="error-box">
                        ❌ 업로드 실패!
                    </div>
                    """, unsafe_allow_html=True)

with tab1:
    st.header("🎨 헤어 스타일 변경")
    
    # 시드 목록 조회
    seeds_data = get_user_seeds(st.session_state.user_id)
    seeds = seeds_data.get("seeds", [])
    
    if not seeds:
        st.warning("먼저 시드 이미지를 업로드해주세요!")
        st.page_link("app.py", label="시드 업로드 탭으로 이동", icon="📸")
    else:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("1️⃣ 시드 이미지 선택")
            
            seed_options = {f"{s['filename']} ({s['created_at'][:16]})": s['id'] for s in seeds}
            selected_seed_name = st.selectbox("시드 선택", list(seed_options.keys()))
            selected_seed_id = seed_options[selected_seed_name]
            
            # 시드 이미지 미리보기
            try:
                seed_response = requests.get(f"{API_BASE}/seed-image/{selected_seed_id}")
                if seed_response.status_code == 200:
                    seed_image = Image.open(io.BytesIO(seed_response.content))
                    st.image(seed_image, caption="선택된 시드 이미지", width=250)
            except:
                st.error("시드 이미지를 불러올 수 없습니다.")
        
        with col2:
            st.subheader("2️⃣ 헤어 참조 이미지")
            
            ref_file = st.file_uploader(
                "헤어 참조 이미지 선택", 
                type=['png', 'jpg', 'jpeg'],
                help="원하는 헤어스타일이 담긴 이미지"
            )
            
            if ref_file:
                ref_image = Image.open(ref_file)
                st.image(ref_image, caption="참조 이미지", width=250)
        
        # 처리 버튼
        if ref_file:
            st.divider()
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("🚀 헤어 변경 시작", type="primary", use_container_width=True):
                    with st.spinner("AI가 헤어스타일을 변경 중입니다... (30-60초 소요)"):
                        
                        # 진행률 표시
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        for i in range(100):
                            progress_bar.progress(i + 1)
                            if i < 20:
                                status_text.text("이미지 분석 중...")
                            elif i < 50:
                                status_text.text("헤어스타일 추출 중...")
                            elif i < 80:
                                status_text.text("AI 변환 처리 중...")
                            else:
                                status_text.text("결과 생성 중...")
                            time.sleep(0.1)
                        
                        # 실제 처리
                        response = process_hair_transfer(selected_seed_id, ref_file)
                        
                        if response:
                            progress_bar.progress(100)
                            status_text.text("완료!")
                            
                            # 결과 표시
                            result_image = Image.open(io.BytesIO(response.content))
                            
                            st.success("✨ 헤어 변경 완료!")
                            
                            # 결과 이미지 표시
                            col1, col2, col3 = st.columns([1, 2, 1])
                            with col2:
                                st.image(result_image, caption="변경 결과", width=400)
                                
                                # 다운로드 버튼
                                img_buffer = io.BytesIO()
                                result_image.save(img_buffer, format='PNG')
                                st.download_button(
                                    "💾 결과 다운로드",
                                    img_buffer.getvalue(),
                                    f"hair_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                                    "image/png",
                                    use_container_width=True
                                )
                        else:
                            st.error("처리에 실패했습니다. 다시 시도해주세요.")

with tab3:
    st.header("📝 처리 기록")
    
    history_data = get_processing_history(st.session_state.user_id)
    history = history_data.get("history", [])
    
    if not history:
        st.info("아직 처리 기록이 없습니다.")
    else:
        st.write(f"총 {len(history)}개의 처리 기록")
        
        for item in history:
            with st.expander(f"🕐 {item['created_at']} - {item['status']}"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**시드 파일:** {item['seed_filename']}")
                
                with col2:
                    st.write(f"**참조 파일:** {item['ref_filename']}")
                
                with col3:
                    status_emoji = {"completed": "✅", "processing": "⏳", "failed": "❌"}
                    st.write(f"**상태:** {status_emoji.get(item['status'], '❓')} {item['status']}")
                
                # 완료된 결과 표시
                if item['status'] == 'completed':
                    try:
                        result_response = requests.get(f"{API_BASE}/result/{item['id']}")
                        if result_response.status_code == 200:
                            result_image = Image.open(io.BytesIO(result_response.content))
                            st.image(result_image, caption="처리 결과", width=300)
                            
                            # 다운로드 버튼
                            img_buffer = io.BytesIO()
                            result_image.save(img_buffer, format='PNG')
                            st.download_button(
                                "다운로드",
                                img_buffer.getvalue(),
                                f"result_{item['id']}.png",
                                "image/png",
                                key=f"download_{item['id']}"
                            )
                    except:
                        st.error("결과 이미지를 불러올 수 없습니다.")

with tab4:
    st.header("ℹ️ 서비스 정보")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 🎯 주요 기능
        - **AI 헤어스타일 변경**: 최신 AI 기술로 자연스러운 헤어스타일 변환
        - **다중 시드 관리**: 여러 개의 시드 이미지를 저장하고 관리
        - **처리 기록**: 이전 변환 결과를 저장하고 다시 다운로드
        - **실시간 처리**: 빠른 속도로 고품질 결과 제공
        """)
        
        st.markdown("""
        ### 💡 사용 팁
        - 정면을 바라보는 고화질 사진 사용
        - 머리카락이 명확히 보이는 이미지 선택
        - 조명이 밝고 균일한 사진 권장
        - 배경이 단순한 이미지가 더 좋은 결과
        """)
    
    with col2:
        st.markdown("""
        ### 🔧 기술 스택
        - **Backend**: FastAPI + SQLite
        - **Frontend**: Streamlit
        - **AI Engine**: VModel API
        - **Image Processing**: PIL/Pillow
        """)
        
        st.markdown("""
        ### 📊 서비스 상태
        """)
        
        # 상태 체크
        if check_api_connection():
            st.success("🟢 API 서버 연결됨")
        else:
            st.error("🔴 API 서버 연결 실패")
        
        # 사용자 통계
        seeds_count = len(get_user_seeds(st.session_state.user_id).get("seeds", []))
        history_count = len(get_processing_history(st.session_state.user_id).get("history", []))
        
        st.metric("등록된 시드 이미지", seeds_count)
        st.metric("처리 기록", history_count)

# 푸터
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; padding: 1rem;">
    💇‍♀️ AI Hair Style Transfer MVP v1.0 | 
    Made with ❤️ using Streamlit & FastAPI
</div>
""", unsafe_allow_html=True)
