import streamlit as st
import requests
from PIL import Image, ImageDraw
import io
import base64
import time
import uuid
from datetime import datetime

# 페이지 설정
st.set_page_config(
    page_title="AI 헤어스타일 변경 서비스",
    page_icon="💇‍♀️",
    layout="wide"
)

# 스타일링
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton > button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 20px;
        padding: 0.5rem 2rem;
        font-weight: bold;
    }
    .success-box {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
    .info-box {
        background: #d1ecf1;
        color: #0c5460;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #bee5eb;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]
    
if 'seed_images' not in st.session_state:
    st.session_state.seed_images = {}
    
if 'processing_history' not in st.session_state:
    st.session_state.processing_history = []

# VModel API 설정 (비밀키는 Streamlit Secrets에서 관리)
VMODEL_API_KEY = st.secrets.get("VMODEL_API_KEY", "")

def validate_image(image):
    """이미지 유효성 검사"""
    try:
        if image.size[0] < 100 or image.size[1] < 100:
            return False, "이미지 크기가 너무 작습니다 (최소 100x100)"
        
        if image.size[0] > 2048 or image.size[1] > 2048:
            return False, "이미지 크기가 너무 큽니다 (최대 2048x2048)"
        
        return True, "유효한 이미지입니다"
    except Exception as e:
        return False, f"이미지 검증 실패: {e}"

def upload_image_to_temp_url(image):
    """임시 이미지 URL 생성 (실제로는 외부 이미지 호스팅 서비스 필요)"""
    # 임시 방편: 이미지를 base64로 변환하되 data URL로 처리
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    b64_string = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{b64_string}"

def process_with_vmodel_api(seed_image, ref_image):
    """VModel API로 헤어 변경 처리"""
    
    if not VMODEL_API_KEY:
        st.error("⚠️ VModel API 키가 설정되지 않았습니다. Streamlit Secrets에서 VMODEL_API_KEY를 설정해주세요.")
        return None
    
    try:
        # 이미지를 임시 URL로 변환 (실제로는 외부 호스팅 필요)
        target_url = upload_image_to_temp_url(seed_image)
        swap_url = upload_image_to_temp_url(ref_image)
        
        # VModel API 페이로드 (문서 형식에 맞춤)
        payload = {
            "version": "d4f292d1ea72ac4e501e6ac7be938ce2a5c50c6852387b1b64dedee01e623029",
            "input": {
                "target_image": target_url,
                "swap_image": swap_url
            }
        }
        
        headers = {
            "Authorization": f"Bearer {VMODEL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Task 생성 API 호출
        response = requests.post(
            "https://api.vmodel.ai/api/tasks/v1/create", 
            json=payload, 
            headers=headers, 
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # 응답 구조 확인
            if result.get('code') == 200 and 'result' in result:
                task_id = result['result'].get('task_id')
                if task_id:
                    return poll_vmodel_task(task_id)
            
        # 에러 응답 표시
        try:
            error_data = response.json()
            st.error(f"API 오류: {error_data}")
        except:
            st.error(f"API 호출 실패: HTTP {response.status_code}")
        
        return None
        
    except Exception as e:
        st.error(f"처리 중 오류 발생: {e}")
        return None

def poll_vmodel_task(task_id, max_attempts=30):
    """VModel 결과 폴링"""
    headers = {"Authorization": f"Bearer {VMODEL_API_KEY}"}
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for attempt in range(max_attempts):
        try:
            response = requests.get(
                f"https://api.vmodel.ai/api/tasks/v1/{task_id}", 
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                status = result.get('status', 'processing')
                
                # 진행률 업데이트
                progress = min(95, (attempt + 1) * 3)
                progress_bar.progress(progress)
                status_text.text(f"AI 처리 중... ({progress}%)")
                
                if status == 'succeeded':
                    progress_bar.progress(100)
                    status_text.text("완료!")
                    
                    result_url = result.get('output', {}).get('image')
                    if result_url:
                        img_response = requests.get(result_url)
                        return Image.open(io.BytesIO(img_response.content))
                
                elif status == 'failed':
                    st.error("처리 실패")
                    return None
                
                time.sleep(2)
            
        except Exception as e:
            if attempt == max_attempts - 1:
                st.error(f"처리 시간 초과: {e}")
                return None
            time.sleep(2)
    
    st.error("처리 시간 초과")
    return None

# 메인 UI
st.markdown("""
<div class="main-header">
    <h1>💇‍♀️ AI 헤어스타일 변경 서비스</h1>
    <p>AI로 원하는 헤어스타일을 미리 체험해보세요!</p>
</div>
""", unsafe_allow_html=True)

# API 키 체크
if not VMODEL_API_KEY:
    st.error("""
    ⚠️ **VModel API 키가 필요합니다!**
    
    1. [VModel.ai](https://vmodel.ai)에서 API 키 발급
    2. Streamlit Cloud 대시보드 → Settings → Secrets
    3. 다음 내용 추가:
    ```
    VMODEL_API_KEY = "your-api-key-here"
    ```
    """)
    st.stop()

# 사이드바
with st.sidebar:
    st.header("🎛️ 설정")
    st.info(f"사용자 ID: {st.session_state.user_id}")
    
    if st.button("🔄 새 세션 시작"):
        st.session_state.clear()
        st.rerun()
    
    st.divider()
    
    st.markdown("""
    ### 📋 사용 방법
    1. **시드 이미지 업로드** (본인 얼굴)
    2. **참조 이미지 업로드** (원하는 헤어스타일)
    3. **AI 변환 실행**
    4. **결과 확인 및 다운로드**
    
    ### 💡 팁
    - 정면을 바라보는 고화질 사진 사용
    - 머리카락이 명확히 보이는 이미지
    - 배경이 단순한 사진 권장
    """)

# 메인 탭
tab1, tab2, tab3 = st.tabs(["🎨 헤어 변경", "📸 시드 관리", "📝 처리 기록"])

with tab2:
    st.header("📸 시드 이미지 관리")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        seed_file = st.file_uploader(
            "시드 이미지 업로드 (본인 얼굴)", 
            type=['png', 'jpg', 'jpeg'],
            help="정면을 바라보는 얼굴 사진"
        )
        
        if seed_file:
            seed_image = Image.open(seed_file)
            st.image(seed_image, caption="미리보기", width=300)
            
            # 이미지 정보
            st.caption(f"파일명: {seed_file.name}")
            st.caption(f"크기: {seed_image.size}")
            
            # 유효성 검사
            is_valid, message = validate_image(seed_image)
            if is_valid:
                st.success(message)
            else:
                st.error(message)
    
    with col2:
        if seed_file and st.button("💾 시드 저장", type="primary"):
            seed_image = Image.open(seed_file)
            is_valid, message = validate_image(seed_image)
            
            if is_valid:
                # 세션에 저장
                seed_id = str(uuid.uuid4())[:8]
                st.session_state.seed_images[seed_id] = {
                    'image': seed_image,
                    'filename': seed_file.name,
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                st.markdown(f"""
                <div class="success-box">
                    ✅ 시드 저장 완료!<br>
                    ID: {seed_id}
                </div>
                """, unsafe_allow_html=True)
                time.sleep(1)
                st.rerun()
            else:
                st.error(message)
    
    # 저장된 시드 목록
    if st.session_state.seed_images:
        st.divider()
        st.subheader("💾 저장된 시드 이미지")
        
        for seed_id, seed_data in st.session_state.seed_images.items():
            with st.expander(f"🖼️ {seed_data['filename']} ({seed_data['created_at']})"):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.image(seed_data['image'], width=200)
                
                with col2:
                    st.write(f"**ID**: {seed_id}")
                    st.write(f"**크기**: {seed_data['image'].size}")
                    
                    if st.button(f"🗑️ 삭제", key=f"delete_{seed_id}"):
                        del st.session_state.seed_images[seed_id]
                        st.rerun()

with tab1:
    st.header("🎨 헤어스타일 변경")
    
    if not st.session_state.seed_images:
        st.warning("먼저 시드 이미지를 업로드해주세요!")
        st.info("👈 **시드 관리** 탭에서 시드 이미지를 추가하세요")
    else:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("1️⃣ 시드 이미지 선택")
            
            seed_options = {
                f"{data['filename']} ({data['created_at']})": seed_id 
                for seed_id, data in st.session_state.seed_images.items()
            }
            
            selected_seed_name = st.selectbox("시드 선택", list(seed_options.keys()))
            selected_seed_id = seed_options[selected_seed_name]
            selected_seed_data = st.session_state.seed_images[selected_seed_id]
            
            st.image(selected_seed_data['image'], caption="선택된 시드", width=250)
        
        with col2:
            st.subheader("2️⃣ 헤어 참조 이미지")
            
            ref_file = st.file_uploader(
                "원하는 헤어스타일 이미지", 
                type=['png', 'jpg', 'jpeg'],
                help="원하는 헤어스타일이 담긴 사진"
            )
            
            if ref_file:
                ref_image = Image.open(ref_file)
                st.image(ref_image, caption="참조 이미지", width=250)
        
        # 처리 실행
        if ref_file:
            st.divider()
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("🚀 AI 헤어 변경 시작", type="primary", use_container_width=True):
                    
                    ref_image = Image.open(ref_file)
                    
                    # 참조 이미지 유효성 검사
                    is_valid, message = validate_image(ref_image)
                    if not is_valid:
                        st.error(f"참조 이미지 오류: {message}")
                        st.stop()
                    
                    with st.spinner("AI가 헤어스타일을 변경하고 있습니다..."):
                        start_time = time.time()
                        
                        # AI 처리
                        result_image = process_with_vmodel_api(
                            selected_seed_data['image'], 
                            ref_image
                        )
                        
                        processing_time = time.time() - start_time
                        
                        if result_image:
                            st.success(f"✨ 헤어 변경 완료! (소요시간: {processing_time:.1f}초)")
                            
                            # 처리 기록 저장
                            history_item = {
                                'id': str(uuid.uuid4())[:8],
                                'seed_filename': selected_seed_data['filename'],
                                'ref_filename': ref_file.name,
                                'result_image': result_image,
                                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'processing_time': processing_time
                            }
                            st.session_state.processing_history.append(history_item)
                            
                            # 결과 표시
                            col1, col2, col3 = st.columns([1, 2, 1])
                            with col2:
                                st.image(result_image, caption="변경 결과", width=400)
                                
                                # 다운로드
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
                            st.error("헤어 변경에 실패했습니다. 다시 시도해주세요.")

with tab3:
    st.header("📝 처리 기록")
    
    if not st.session_state.processing_history:
        st.info("아직 처리 기록이 없습니다.")
    else:
        st.write(f"총 {len(st.session_state.processing_history)}개의 처리 기록")
        
        # 최신 순으로 정렬
        history = sorted(
            st.session_state.processing_history, 
            key=lambda x: x['created_at'], 
            reverse=True
        )
        
        for item in history:
            with st.expander(f"🕐 {item['created_at']} - {item['seed_filename']} → {item['ref_filename']}"):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.write(f"**처리 ID**: {item['id']}")
                    st.write(f"**시드 파일**: {item['seed_filename']}")
                    st.write(f"**참조 파일**: {item['ref_filename']}")
                    st.write(f"**처리 시간**: {item['processing_time']:.1f}초")
                
                with col2:
                    st.image(item['result_image'], caption="처리 결과", width=300)
                    
                    # 다운로드
                    img_buffer = io.BytesIO()
                    item['result_image'].save(img_buffer, format='PNG')
                    st.download_button(
                        "다운로드",
                        img_buffer.getvalue(),
                        f"result_{item['id']}.png",
                        "image/png",
                        key=f"download_{item['id']}"
                    )

# 푸터
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; padding: 1rem;">
    💇‍♀️ AI Hair Style Transfer | Made with ❤️ using Streamlit Cloud<br>
    <small>세션 종료시 데이터가 삭제됩니다. 중요한 결과는 다운로드하세요!</small>
</div>
""", unsafe_allow_html=True)
