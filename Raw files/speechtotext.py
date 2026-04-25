"""
================================================================================
Volvo 음성 제어 시스템 (Voice Control System) - faster-whisper 버전
================================================================================

[변경 사항]
- STT: Groq Whisper (클라우드) → faster-whisper (로컬 GPU)
- 장점: 네트워크 지연 없음, 보안 강화, 오프라인 사용 가능

[시스템 개요]
- Wake Word: "Hey Volvo" (Porcupine)
- 화자 검증: Eagle (Picovoice) - 등록된 사용자만 인식
- STT: faster-whisper (로컬 GPU)
- TTS: edge-tts (Microsoft, 한국어 여성 음성)

================================================================================
Jetson Orin NX 설치 가이드 (JetPack 5.x / CUDA 11.4 기준)
================================================================================

[STEP 1] 가상환경 생성 (권장)
-------------------------------------------------
cd ~/Desktop/capstone/volvo-1/volvo
python3 -m venv pre.venv
source pre.venv/bin/activate

[STEP 2] 기본 패키지 설치
-------------------------------------------------
pip install --upgrade pip
pip install numpy pyaudio pvporcupine pveagle python-dotenv edge-tts nest_asyncio

[STEP 3] faster-whisper 설치 (Jetson 전용)
-------------------------------------------------
# Jetson은 CUDA 11.4를 사용하므로 ctranslate2 버전 호환성 주의
# 참고: https://github.com/SYSTRAN/faster-whisper

# 방법 1: ctranslate2 3.24.0 (CUDA 11.4 + cuDNN 8 호환)
pip install ctranslate2==3.24.0
pip install faster-whisper

# 방법 2: 최신 버전 시도 (JetPack 6.0+ / CUDA 12인 경우)
# pip install faster-whisper

[STEP 4] cuDNN 확인 (Jetson에서 필수)
-------------------------------------------------
# cuDNN이 설치되어 있는지 확인
dpkg -l | grep cudnn

# 없으면 JetPack SDK Manager로 설치하거나:
# sudo apt install libcudnn8 libcudnn8-dev

[STEP 5] 모델 다운로드 (첫 실행 시 자동)
-------------------------------------------------
# 모델은 첫 실행 시 자동으로 ~/.cache/huggingface/hub에 다운로드됩니다.
# 수동 다운로드 원하면:
# python3 -c "from faster_whisper import WhisperModel; WhisperModel('large-v3')"

[STEP 6] .env 파일 설정
-------------------------------------------------
# /home/comfuture/Desktop/capstone/volvo-1/volvo/.env 파일에:
PORCUPINE_ACCESS_KEY=your_picovoice_access_key

# 참고: Groq API Key는 더 이상 필요 없음 (로컬 STT 사용)

[STEP 7] 실행
-------------------------------------------------
python3 first_STT_kw_faster_whisper.py

================================================================================
모델별 VRAM 사용량 (출처: faster-whisper GitHub, HuggingFace)
================================================================================
| 모델               | VRAM (FP16) | VRAM (INT8) | 정확도     | 속도   |
|--------------------|-------------|-------------|------------|--------|
| tiny               | ~1GB        | ~0.5GB      | 낮음       | 매우빠름|
| base               | ~1.5GB      | ~1GB        | 낮음       | 빠름   |
| small              | ~2.5GB      | ~1.5GB      | 중간       | 빠름   |
| medium             | ~5GB        | ~3GB        | 좋음       | 중간   |
| large-v3           | ~10GB       | ~6GB        | 최고       | 느림   |
| large-v3-turbo     | ~6GB        | ~4GB        | 좋음       | 빠름   |
| distil-large-v3    | ~4GB        | ~2.5GB      | 좋음       | 빠름   |

[Jetson Orin NX 16GB 권장]
- large-v3 (FP16): 최고 정확도, ~10GB 사용, 충분히 실행 가능
- large-v3-turbo: 균형 잡힌 선택, ~6GB 사용
- distil-large-v3: 영어 전용, ~4GB 사용, 빠름

[모델 변경 방법]
코드에서 MODEL_SIZE 변수만 바꾸면 됩니다:
MODEL_SIZE = "large-v3"        # 최고 정확도
MODEL_SIZE = "large-v3-turbo"  # 속도-정확도 균형
MODEL_SIZE = "medium"          # VRAM 절약

================================================================================
★★★ THREADING 가이드 (다른 모듈과 통합 시 필독) ★★★
================================================================================

이 코드를 다른 모듈(LLM, AC Controller 등)과 통합하려면 Thread로 감싸야 합니다.
아래는 클래스로 변환하는 방법과 주의사항입니다.

[1] 클래스 구조 예시
-------------------------------------------------
import threading

class VoiceRecognition:
    '''
    음성 인식을 별도 스레드에서 실행하는 클래스

    사용법:
        voice = VoiceRecognition()
        voice.start()           # 스레드 시작 (등록 + 메인 루프)
        ...
        print(voice.last_command)  # 마지막 STT 결과 확인
        voice.stop()            # 종료
    '''

    def __init__(self):
        # === 공유 변수 (다른 스레드에서 접근 가능) ===
        self.running = False          # 실행 상태 플래그
        self.last_command = ""        # 마지막 STT 결과 (다른 모듈에서 읽기)
        self.is_listening = False     # 현재 듣는 중인지
        self.is_registered = False    # 사용자 등록 완료 여부

        # === 내부 변수 (이 클래스 내부에서만 사용) ===
        self._thread = None
        self._eagle = None
        self._porcupine = None
        self._stream = None
        self._pa = None

    def start(self):
        '''스레드 시작'''
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        '''스레드 종료 (리소스 해제는 _run 내부 finally에서 처리)'''
        self.running = False
        if self._thread:
            self._thread.join(timeout=5.0)  # 최대 5초 대기

    def _run(self):
        '''
        실제 실행 로직 (register_and_run 함수 내용)
        주의: while True → while self.running 으로 변경해야 함
        '''
        try:
            # ... 등록 로직 ...
            self.is_registered = True

            # ... 메인 루프 ...
            while self.running:  # ← 핵심! True 대신 self.running 사용
                # Wake Word 감지
                # 화자 검증
                # STT
                self.last_command = text  # ← 결과를 공유 변수에 저장

        finally:
            # 리소스 해제
            self._cleanup()

    def _cleanup(self):
        '''리소스 해제'''
        if self._eagle:
            self._eagle.delete()
        if self._porcupine:
            self._porcupine.delete()
        if self._stream:
            self._stream.close()
        if self._pa:
            self._pa.terminate()

[2] 다른 모듈에서 사용하는 방법
-------------------------------------------------
# main.py (통합 코드)
from voice_recognition import VoiceRecognition
from ac_controller import ACController

# 각 모듈 초기화
voice = VoiceRecognition()
ac = ACController()

# 스레드 시작
voice.start()
ac.start()

# 메인 루프에서 voice.last_command 감시
while True:
    if voice.last_command:
        ac.process_command(voice.last_command)
        voice.last_command = ""  # 처리 후 초기화
    time.sleep(0.1)

[3] 공유 변수 설명
-------------------------------------------------
| 변수명          | 타입   | 용도                              | 접근 방향      |
|-----------------|--------|-----------------------------------|----------------|
| running         | bool   | 스레드 실행/종료 제어             | 쓰기: 외부     |
| last_command    | str    | STT 결과 텍스트                   | 읽기: 외부     |
| is_listening    | bool   | 현재 음성 녹음 중인지             | 읽기: 외부     |
| is_registered   | bool   | 사용자 등록 완료 여부             | 읽기: 외부     |

[4] Thread-Safe 주의사항
-------------------------------------------------
- last_command는 단순 문자열이므로 Lock 없이 사용 가능
- 복잡한 데이터(리스트, 딕셔너리)를 공유하려면 threading.Lock() 사용 권장
- 예시:
    self._lock = threading.Lock()
    with self._lock:
        self.shared_data.append(item)

[5] 파일 기반 통신 (현재 방식)
-------------------------------------------------
현재 코드는 latest_command.txt 파일을 통해 LLM 모듈과 통신합니다.
- 장점: 간단하고 디버깅 쉬움
- 단점: 파일 I/O 오버헤드
- 위치: /home/comfuture/Desktop/capstone/volvo-1/LLMtoFunction/latest_command.txt

Thread 방식으로 전환하면 파일 대신 공유 변수(self.last_command)를 사용할 수 있습니다.

================================================================================
"""

# %% ============================================================================
# [1] 설정 및 라이브러리 임포트
# ==============================================================================
#
# ★ THREADING 가이드 ★
# 이 섹션은 모듈 최상단에 위치해야 합니다.
# 클래스로 감쌀 때: 이 부분은 클래스 외부(모듈 레벨)에 그대로 둡니다.
#
# 이유:
# - import는 모듈 로드 시 한 번만 실행되어야 함
# - whisper_model은 무거우므로 전역으로 한 번만 로드
# - 경로 설정(BASE_DIR 등)도 전역 상수로 유지
#
# ==============================================================================

import os
import time
import datetime
import wave
import subprocess
import numpy as np
import pyaudio
import pvporcupine
import pveagle
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# --- [faster-whisper 임포트] ---
# ★ THREADING: 이 부분은 모듈 레벨에 유지 (클래스 안에 넣지 않음)
try:
    from faster_whisper import WhisperModel

    FASTER_WHISPER_AVAILABLE = True
    print("✅ faster-whisper 사용 가능")
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    print("❌ faster-whisper 설치 필요: pip install faster-whisper")
    print("   Jetson의 경우: pip install ctranslate2==3.24.0 && pip install faster-whisper")
    exit(1)

# --- [경로 설정] ---
# ★ THREADING: 전역 상수로 유지 (클래스 안에서도 접근 가능)
# 다른 환경에서 사용 시 BASE_DIR만 수정하면 됨
BASE_DIR = Path("/home/comfuture/Desktop/capstone/volvo-1")
VOICE_DIR = BASE_DIR / "voice"  # TTS, WAV 저장 폴더
KW_PATH = BASE_DIR / "volvo" / "heyvolvo.ppn"  # Wake Word 모델
MODEL_PATH = BASE_DIR / "volvo" / "porcupine_params_ko.pv"  # Porcupine 한국어 모델
EAGLE_PROFILE_PATH = BASE_DIR / "volvo" / "eagle_speaker.profile"  # 화자 프로필
CMD_PATH = BASE_DIR / "LLMtoFunction" / "latest_command.txt"  # STT 결과 저장 (LLM 연동)
ENV_PATH = BASE_DIR / "volvo" / ".env"  # API 키 파일

# 폴더 생성
VOICE_DIR.mkdir(exist_ok=True, parents=True)
CMD_PATH.parent.mkdir(exist_ok=True, parents=True)

# --- [API 키 로드] ---
# ★ THREADING: 전역으로 유지 (한 번만 로드)
load_dotenv(ENV_PATH, override=True)
PICOVOICE_KEY = os.getenv("PORCUPINE_ACCESS_KEY") or os.getenv("PICOVOICE_ACCESS_KEY")

if not PICOVOICE_KEY:
    raise ValueError("ERROR: .env 파일에서 PORCUPINE_ACCESS_KEY를 찾을 수 없습니다.")

# --- [faster-whisper 설정] ---
# ★ THREADING: 모델은 전역으로 한 번만 로드 (매우 중요!)
#   - 모델 로드는 수 초 ~ 수십 초 소요
#   - 메모리를 많이 사용 (large-v3: ~10GB VRAM)
#   - 스레드마다 로드하면 메모리 부족 발생
#
# 모델 크기 선택 (이 변수만 바꾸면 다른 모델 사용 가능)
# 옵션: "tiny", "base", "small", "medium", "large-v2", "large-v3", "large-v3-turbo", "distil-large-v3"
MODEL_SIZE = "large-v3"

# compute_type 옵션:
# - "float16": 기본값, 좋은 성능 (GPU 필수)
# - "int8_float16": 메모리 절약, 약간의 정확도 손실 (GPU 필수)
# - "int8": CPU에서도 사용 가능, 메모리 최소
# - "float32": CPU 전용, 가장 정확하지만 느림
COMPUTE_TYPE = "float16"

# device 옵션: "cuda" (GPU) 또는 "cpu"
DEVICE = "cuda"

print(f"\n🔄 faster-whisper 모델 로딩 중: {MODEL_SIZE} (device={DEVICE}, compute_type={COMPUTE_TYPE})")
print("   (첫 실행 시 모델 다운로드로 시간이 걸릴 수 있습니다...)")

# ★ THREADING: 전역 모델 객체 (모든 스레드에서 공유)
#   - Thread-safe: faster-whisper의 transcribe()는 내부적으로 thread-safe
#   - 동시 호출 시 순차 처리됨 (GPU 연산이므로 병렬화 불가)
whisper_model = WhisperModel(
    MODEL_SIZE,
    device=DEVICE,
    compute_type=COMPUTE_TYPE
)
print(f"✅ faster-whisper 모델 로드 완료: {MODEL_SIZE}")

# --- [오디오 설정] ---
SR = 16000  # 샘플레이트 (Porcupine/Eagle 기본값)

print(f"✅ 라이브러리 로드 및 설정 완료")
print(f"   BASE_DIR: {BASE_DIR}")
print(f"   CMD_PATH: {CMD_PATH}")

# %% ============================================================================
# [2] 유틸리티 함수 (TTS, 오디오 처리)
# ==============================================================================
#
# ★ THREADING 가이드 ★
# 이 함수들은 stateless (상태를 저장하지 않음)이므로 스레드 간 공유 가능합니다.
#
# 클래스로 감쌀 때 두 가지 선택:
#   1. 그대로 전역 함수로 유지 (권장)
#   2. 클래스의 @staticmethod로 변환
#
# 예시 (@staticmethod 변환):
#   class VoiceRecognition:
#       @staticmethod
#       def rms(pcm):
#           return np.sqrt(np.mean((pcm.astype(np.float32) / 32768) ** 2) + 1e-12)
#
# ==============================================================================

# --- [TTS 설정] ---
try:
    import edge_tts

    USE_EDGE_TTS = True
    print("✅ edge-tts 사용 가능")
except ImportError:
    USE_EDGE_TTS = False
    print("⚠️ edge-tts 없음 - gTTS 사용")
    from gtts import gTTS

VOICE_NAME = "ko-KR-SunHiNeural"  # 한국어 여성 음성


def make_tts(text: str, filename: str) -> Path:
    """
    텍스트를 음성 파일(mp3)로 변환

    ★ THREADING: Thread-safe (파일 시스템 접근만 함)
      - 같은 파일을 동시에 생성하지 않도록 주의
      - 이미 존재하면 재사용하므로 대부분 안전

    Args:
        text: 변환할 텍스트
        filename: 저장할 파일명

    Returns:
        생성된 파일 경로
    """
    path = VOICE_DIR / filename

    # 이미 존재하면 재사용
    if path.exists() and path.stat().st_size > 1000:
        return path

    print(f"[TTS] 생성 중: '{text}'")

    if USE_EDGE_TTS:
        # edge-tts CLI 사용 (가장 안정적)
        cmd = ["edge-tts", "--voice", VOICE_NAME, "--text", text, "--write-media", str(path)]
        subprocess.run(cmd, capture_output=True, text=True)
        if path.exists():
            return path

    # 폴백: gTTS
    try:
        from gtts import gTTS
        gTTS(text=text, lang='ko', tld='co.kr').save(str(path))
    except Exception as e:
        print(f"[TTS] 실패: {e}")

    return path


def play_audio(path, block: bool = True):
    """
    오디오 파일 재생

    ★ THREADING: 주의 필요!
      - block=True: 재생 완료까지 현재 스레드 블로킹
      - block=False: 백그라운드 재생 (subprocess.Popen)
      - 동시에 여러 오디오 재생 시 겹칠 수 있음

    Args:
        path: 재생할 파일 경로
        block: True면 재생 완료까지 대기, False면 백그라운드 재생
    """
    path = Path(path)
    if not path.exists():
        return

    try:
        if block:
            subprocess.run(["mpg123", "-q", str(path)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        else:
            subprocess.Popen(["mpg123", "-q", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[재생 오류] {e}")


def rms(pcm: np.ndarray) -> float:
    """
    오디오 신호의 RMS(Root Mean Square) 에너지 계산
    음성 감지(VAD)에 사용

    ★ THREADING: 완전 Thread-safe (순수 함수, 부작용 없음)

    Args:
        pcm: int16 오디오 데이터

    Returns:
        RMS 값 (0.0 ~ 1.0)
    """
    return np.sqrt(np.mean((pcm.astype(np.float32) / 32768) ** 2) + 1e-12)


def save_wav(path, frames: list):
    """
    녹음된 프레임을 WAV 파일로 저장

    ★ THREADING: Thread-safe (파일 시스템 접근)
      - 같은 경로에 동시 쓰기하지 않도록 타임스탬프 사용 권장

    Args:
        path: 저장 경로
        frames: 바이트 프레임 리스트
    """
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16bit
        w.setframerate(SR)
        w.writeframes(b''.join(frames))


def transcribe_audio(wav_path: str) -> str:
    """
    faster-whisper를 사용하여 음성을 텍스트로 변환

    ★ THREADING: Thread-safe
      - whisper_model은 전역 객체이지만 transcribe()는 내부적으로 thread-safe
      - GPU 연산이므로 동시 호출 시 순차 처리 (자동 큐잉)
      - 여러 스레드에서 동시 호출해도 안전하지만 속도 이점은 없음

    Args:
        wav_path: WAV 파일 경로

    Returns:
        변환된 텍스트 (실패 시 빈 문자열)
    """
    try:
        # faster-whisper로 변환
        # vad_filter=True: 무음 구간 자동 제거
        # language="ko": 한국어 지정 (자동 감지보다 빠름)
        segments, info = whisper_model.transcribe(
            str(wav_path),
            language="ko",
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,  # 0.5초 이상 침묵 시 분리
            ),
            beam_size=5,  # 정확도 vs 속도 균형 (1~10, 기본 5)
        )

        # segments는 generator이므로 리스트로 변환하여 텍스트 추출
        text_parts = [segment.text for segment in segments]
        text = " ".join(text_parts).strip()

        return text

    except Exception as e:
        print(f"[STT Error] {e}")
        return ""


def get_audio_device() -> int:
    """
    사용 가능한 마이크 디바이스 인덱스 반환
    우선순위: pulse > bluez > usb > 기본

    ★ THREADING: Thread-safe
      - PyAudio 객체를 함수 내부에서 생성/종료
      - 전역 상태 변경 없음

    Returns:
        디바이스 인덱스 (없으면 None)
    """
    pa = pyaudio.PyAudio()
    dev_index = None

    print("\n=== 오디오 디바이스 검색 ===")
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            name = info['name']
            print(f" [{i}] {name}")

            # 우선순위 선택
            if dev_index is None:
                name_lower = name.lower()
                if 'pulse' in name_lower and 'monitor' not in name_lower:
                    dev_index = i
                    print(f"   >>> 선택됨")

    pa.terminate()
    return dev_index


print("✅ 유틸리티 함수 로드 완료")


# %% ============================================================================
# [3] 사용자 등록 + 메인 실행 루프
# ==============================================================================
#
# ★★★ THREADING 가이드 (핵심!) ★★★
#
# 이 함수(register_and_run)를 스레드에서 실행하려면 아래 수정이 필요합니다:
#
# [수정 1] while True → while self.running
#   현재:  while True:
#   수정:  while self.running:
#   이유:  외부에서 self.running = False로 종료 신호를 보낼 수 있음
#
# [수정 2] STT 결과를 공유 변수에 저장
#   현재:  with open(CMD_PATH, 'w') as f: f.write(text)
#   추가:  self.last_command = text
#   이유:  다른 스레드에서 파일 대신 변수로 직접 접근 가능
#
# [수정 3] 리소스를 인스턴스 변수로 저장
#   현재:  eagle = pveagle.create_recognizer(...)
#   수정:  self._eagle = pveagle.create_recognizer(...)
#   이유:  stop() 메서드에서 리소스 해제 가능
#
# [수정 4] 함수를 클래스 메서드로 변환
#   현재:  def register_and_run():
#   수정:  def _run(self):
#   이유:  self 접근 필요
#
# ==============================================================================

def register_and_run():
    """
    사용자 음성 등록 + 메인 루프 실행

    ★★★ THREADING 변환 가이드 ★★★

    이 함수를 클래스 메서드 _run(self)로 변환할 때:

    1. 지역 변수 → 인스턴스 변수 변환 목록:
       - eagle → self._eagle
       - porcupine → self._porcupine
       - stream → self._stream
       - pa → self._pa
       - energy_thr → self._energy_thr
       - SPEAKER_THRESHOLD → self._speaker_threshold

    2. 결과 공유를 위한 변수 추가:
       - self.last_command = ""  (STT 결과)
       - self.is_listening = False  (현재 상태)
       - self.is_registered = False  (등록 완료 여부)

    3. 메인 루프 수정:
       - while True → while self.running

    4. 종료 처리:
       - finally 블록의 리소스 해제 코드를 _cleanup() 메서드로 분리
       - stop() 메서드에서 self.running = False 후 _cleanup() 호출

    [흐름]
    STEP 1: TTS 파일 생성 (등록 안내, 완료 안내, 응답 음성)
    STEP 2: Eagle로 사용자 음성 등록 (100%까지)
    STEP 3: 배경 소음 측정 → 에너지 임계값 계산
    STEP 4: 메인 루프 (Wake Word → 화자 검증 → STT → 저장)
    """

    # Eagle 피드백 메시지
    FEEDBACK_MSG = {
        pveagle.EagleProfilerEnrollFeedback.AUDIO_OK: "✅ 좋음",
        pveagle.EagleProfilerEnrollFeedback.AUDIO_TOO_SHORT: "⚠️ 너무 짧음",
        pveagle.EagleProfilerEnrollFeedback.UNKNOWN_SPEAKER: "⚠️ 다른 사람?",
        pveagle.EagleProfilerEnrollFeedback.NO_VOICE_FOUND: "⚠️ 음성 없음",
        pveagle.EagleProfilerEnrollFeedback.QUALITY_ISSUE: "⚠️ 품질 문제",
    }

    # ========================================
    # [STEP 1] TTS 파일 생성
    # ========================================
    # ★ THREADING: 이 부분은 __init__() 또는 별도 초기화 메서드로 분리 가능
    #   - TTS 파일은 한 번만 생성하면 되므로 초기화 시 처리
    #   - 또는 첫 실행 시 lazy 생성
    print("\n" + "=" * 60)
    print("STEP 1: TTS 파일 생성")
    print("=" * 60)

    make_tts("안녕하세요를 반복해서 말씀해 주세요", "register_prompt.mp3")
    make_tts("등록이 완료되었습니다", "register_done.mp3")
    make_tts("네, 부르셨나요?", "wake_response.mp3")
    make_tts("네, 확인했습니다", "ack_response.mp3")
    print("✅ TTS 파일 준비 완료")

    # ========================================
    # [STEP 2] Eagle 화자 등록
    # ========================================
    # ★ THREADING: 이 부분은 별도 register_user() 메서드로 분리 권장
    #   - 등록은 한 번만 수행
    #   - 이미 등록된 경우 스킵하는 로직 추가 가능:
    #     if EAGLE_PROFILE_PATH.exists():
    #         print("기존 프로필 사용")
    #         return  # 등록 스킵
    print("\n" + "=" * 60)
    print("STEP 2: 사용자 음성 등록")
    print("=" * 60)

    # Eagle Profiler 초기화
    eagle_profiler = pveagle.create_profiler(access_key=PICOVOICE_KEY)
    print(f"✅ Eagle Profiler 초기화 완료")
    print(f"   min_enroll_samples: {eagle_profiler.min_enroll_samples}")

    # 오디오 스트림 열기
    pa = pyaudio.PyAudio()
    dev_index = get_audio_device()

    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SR,
        input=True,
        frames_per_buffer=eagle_profiler.min_enroll_samples,
        input_device_index=dev_index
    )

    # 등록 안내 재생
    play_audio(VOICE_DIR / "register_prompt.mp3", block=True)

    # 등록 진행 (100%까지 자동)
    print("\n🗣️ '안녕하세요'를 반복해서 말씀해 주세요...\n")

    enroll_percentage = 0.0
    noise_samples = []  # 배경 소음도 함께 측정

    # ★ THREADING: 등록 중에도 self.running 체크 가능
    #   while enroll_percentage < 100.0 and self.running:
    while enroll_percentage < 100.0:
        data = stream.read(eagle_profiler.min_enroll_samples, exception_on_overflow=False)
        pcm = np.frombuffer(data, dtype=np.int16)

        # 배경 소음 측정 (등록 중 에너지 수집)
        noise_samples.append(rms(pcm))

        try:
            enroll_percentage, feedback = eagle_profiler.enroll(list(pcm))
            feedback_str = FEEDBACK_MSG.get(feedback, str(feedback))

            # 진행률 표시
            bar_len = int(enroll_percentage / 100 * 30)
            bar = f"[{'█' * bar_len}{'░' * (30 - bar_len)}]"
            print(f"\r   {bar} {enroll_percentage:.1f}% | {feedback_str}     ", end="")

        except pveagle.EagleError as e:
            print(f"\n   등록 오류: {e}")
            continue

    print(f"\n\n✅ 등록 100% 완료!")

    # 프로필 저장
    try:
        speaker_profile = eagle_profiler.export()
        with open(str(EAGLE_PROFILE_PATH), 'wb') as f:
            f.write(speaker_profile.to_bytes())
        print(f"   프로필 저장: {EAGLE_PROFILE_PATH}")
    except pveagle.EagleError as e:
        print(f"❌ 프로필 저장 실패: {e}")
        eagle_profiler.delete()
        stream.close()
        pa.terminate()
        return

    eagle_profiler.delete()

    # 완료 안내
    play_audio(VOICE_DIR / "register_done.mp3", block=True)

    # ★ THREADING: 등록 완료 상태 업데이트
    #   self.is_registered = True

    # ========================================
    # [STEP 3] 배경 소음 임계값 계산
    # ========================================
    # ★ THREADING: 이 값들을 인스턴스 변수로 저장
    #   self._energy_thr = energy_thr
    #   self._speaker_threshold = SPEAKER_THRESHOLD
    print("\n" + "=" * 60)
    print("STEP 3: 배경 소음 측정")
    print("=" * 60)

    # 등록 중 수집한 샘플로 임계값 계산
    energy_thr = max(0.015, np.median(noise_samples) * 6)
    print(f"✅ Energy threshold: {energy_thr:.5f}")

    # 화자 검증 임계값 (기본값 사용, 진단 생략)
    SPEAKER_THRESHOLD = 0.5
    print(f"✅ Speaker threshold: {SPEAKER_THRESHOLD}")

    stream.close()
    pa.terminate()

    # ========================================
    # [STEP 4] 메인 루프 (Wake Word 대기)
    # ========================================
    # ★ THREADING: 이 부분이 핵심!
    #   - eagle, porcupine, stream, pa를 인스턴스 변수로 저장
    #   - while True → while self.running
    #   - STT 결과를 self.last_command에 저장
    print("\n" + "=" * 60)
    print("STEP 4: 메인 루프 시작")
    print("=" * 60)

    # ★ THREADING: self._eagle = pveagle.create_recognizer(...)
    # Eagle Recognizer 로드
    with open(str(EAGLE_PROFILE_PATH), 'rb') as f:
        speaker_profile = pveagle.EagleProfile.from_bytes(f.read())

    eagle = pveagle.create_recognizer(
        access_key=PICOVOICE_KEY,
        speaker_profiles=[speaker_profile]
    )
    print(f"✅ Eagle Recognizer 로드 완료")

    # ★ THREADING: self._porcupine = pvporcupine.create(...)
    # Porcupine (Wake Word) 초기화
    porcupine = pvporcupine.create(
        access_key=PICOVOICE_KEY,
        keyword_paths=[str(KW_PATH)],
        model_path=str(MODEL_PATH),
        sensitivities=[0.9],  # 민감도 (0.0~1.0, 높을수록 민감)
    )
    print(f"✅ Porcupine 로드 완료 (frame_length: {porcupine.frame_length})")

    # TTS 파일 경로
    tts_wake = VOICE_DIR / "wake_response.mp3"
    tts_ack = VOICE_DIR / "ack_response.mp3"

    # ★ THREADING: self._pa, self._stream
    # 오디오 스트림 열기
    pa = pyaudio.PyAudio()
    dev_index = get_audio_device()

    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SR,
        input=True,
        frames_per_buffer=porcupine.frame_length,
        input_device_index=dev_index
    )

    print(f"\n{'=' * 60}")
    print(f"🎤 READY! >> 'Hey Volvo' 하고 말해보세요.")
    print(f"   STT 엔진: faster-whisper ({MODEL_SIZE})")
    print(f"   종료: Ctrl+C")
    print(f"{'=' * 60}\n")
    print(">> 듣는 중...")

    # ----------------------------------------
    # ★★★ 메인 루프 ★★★
    # THREADING 핵심 수정 포인트:
    #   현재:  while True:
    #   수정:  while self.running:
    #
    # self.running은 외부에서 False로 설정하여 루프 종료 가능
    # 예: voice.stop() 메서드에서 self.running = False
    # ----------------------------------------
    try:
        while True:  # ← THREADING: while self.running: 으로 변경
            # ★ THREADING: self.is_listening = False (대기 상태)

            # Wake Word 감지
            data = stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = np.frombuffer(data, dtype=np.int16)

            if porcupine.process(pcm) >= 0:
                # ★ THREADING: self.is_listening = True (녹음 시작)
                print("\n[WAKE] 'Hey Volvo' 감지!")
                play_audio(tts_wake, block=True)

                # ----------------------------------------
                # 음성 녹음 + 화자 검증
                # ----------------------------------------
                eagle.reset()
                eagle_buffer = []
                frames = []
                started = False
                t0 = time.time()
                last_speech = time.time()
                max_score = 0.0

                # ★ THREADING: 내부 루프도 self.running 체크 가능
                #   while True and self.running:
                while True:
                    data = stream.read(porcupine.frame_length, exception_on_overflow=False)
                    pcm = np.frombuffer(data, dtype=np.int16)
                    frames.append(data)
                    eagle_buffer.extend(pcm.tolist())

                    e = rms(pcm)
                    now = time.time()

                    # 음성 감지 (VAD)
                    if e >= energy_thr:
                        if not started:
                            started = True
                            print("   🗣️ 음성 감지!")
                        last_speech = now

                    # Eagle 화자 검증 (프레임 단위)
                    while len(eagle_buffer) >= eagle.frame_length:
                        eagle_frame = eagle_buffer[:eagle.frame_length]
                        eagle_buffer = eagle_buffer[eagle.frame_length:]

                        try:
                            scores = eagle.process(eagle_frame)
                            score = scores[0]

                            if score > max_score:
                                max_score = score

                            # 실시간 점수 표시
                            if started and score > 0.01:
                                icon = "✅" if score >= SPEAKER_THRESHOLD else "❌"
                                print(f"\r   [Eagle] {score:.3f} (max: {max_score:.3f}) {icon}   ", end="")

                        except pveagle.EagleError:
                            pass

                    # 종료 조건
                    elapsed = now - t0
                    silence = now - last_speech if started else 0

                    if started and silence > 1.5:  # 1.5초 침묵 → 발화 종료
                        print("\n   ✅ 발화 종료")
                        break
                    if not started and elapsed > 3.0:  # 3초간 음성 없음 → 취소
                        print("\n   ⚠️ 음성 없음 - 취소")
                        frames = []
                        break
                    if elapsed > 10.0:  # 최대 10초
                        print("\n   ⚠️ 최대 시간 초과")
                        break

                # ----------------------------------------
                # 후처리: 화자 확인 → STT → 저장
                # ----------------------------------------
                if frames and started:
                    print(f"   [FINAL] Eagle 점수: {max_score:.3f} (threshold: {SPEAKER_THRESHOLD})")

                    # 화자 검증 실패 → 무시
                    if max_score < SPEAKER_THRESHOLD:
                        print("   ❌ 등록된 사용자가 아닙니다. (무시)\n")
                        # ★ THREADING: self.is_listening = False
                        print(">> 듣는 중...")
                        continue

                    # 화자 검증 성공 → "네, 확인했습니다" 재생
                    play_audio(tts_ack, block=True)

                    # WAV 저장
                    ts = datetime.datetime.now().strftime("%H%M%S")
                    wav_path = VOICE_DIR / f"cmd_{ts}.wav"
                    save_wav(wav_path, frames)

                    # STT (faster-whisper - 로컬)
                    print("   📝 텍스트 변환 중 (faster-whisper)...")
                    stt_start = time.time()

                    text = transcribe_audio(wav_path)

                    stt_elapsed = time.time() - stt_start

                    if text:
                        print(f'\n   🗣️ "{text}"')
                        print(f"   ⏱️ STT 소요 시간: {stt_elapsed:.2f}초\n")

                        # ★★★ THREADING 핵심: 결과를 공유 변수에 저장 ★★★
                        # 추가할 코드:
                        #   self.last_command = text
                        #
                        # 다른 스레드에서 접근:
                        #   if voice.last_command:
                        #       process(voice.last_command)
                        #       voice.last_command = ""  # 처리 후 초기화

                        # 파일 기반 통신 (현재 방식, 유지해도 됨)
                        # latest_command.txt 저장 (LLM 시스템 연동)
                        # 다른 모듈에서 이 파일을 감시하여 명령어 처리
                        with open(CMD_PATH, 'w', encoding='utf-8') as f:
                            f.write(text + '\n')
                        print(f"   📁 저장: {CMD_PATH}")
                    else:
                        print("   (내용 없음)\n")

                # ★ THREADING: self.is_listening = False
                print(">> 듣는 중...")

    except KeyboardInterrupt:
        print("\n\n👋 종료")

    finally:
        # ========================================
        # ★★★ 리소스 해제 (THREADING 핵심!) ★★★
        # ========================================
        # THREADING 시 이 부분을 _cleanup() 메서드로 분리:
        #
        # def _cleanup(self):
        #     if self._eagle:
        #         self._eagle.delete()
        #         self._eagle = None
        #     if self._porcupine:
        #         self._porcupine.delete()
        #         self._porcupine = None
        #     if self._stream:
        #         self._stream.close()
        #         self._stream = None
        #     if self._pa:
        #         self._pa.terminate()
        #         self._pa = None
        #
        # stop() 메서드:
        # def stop(self):
        #     self.running = False
        #     # 루프가 종료될 때까지 대기 (최대 5초)
        #     if self._thread and self._thread.is_alive():
        #         self._thread.join(timeout=5.0)
        #
        # 주의: delete()는 한 번만 호출해야 함 (중복 호출 시 에러)
        #       None 체크 후 None으로 설정하여 중복 방지

        if eagle:
            eagle.delete()
        if porcupine:
            porcupine.delete()
        if stream:
            stream.close()
        if pa:
            pa.terminate()
        print("✅ 리소스 해제 완료")


# ============================================================================
# 실행
# ============================================================================
# ★ THREADING: 직접 실행 대신 클래스 인스턴스화
#
# 현재 (단독 실행):
#   if __name__ == "__main__":
#       register_and_run()
#
# THREADING 변환 후:
#   if __name__ == "__main__":
#       voice = VoiceRecognition()
#       voice.start()  # 백그라운드 스레드 시작
#
#       try:
#           while True:
#               if voice.last_command:
#                   print(f"명령어 수신: {voice.last_command}")
#                   # 여기서 LLM 처리 등
#                   voice.last_command = ""
#               time.sleep(0.1)
#       except KeyboardInterrupt:
#           voice.stop()
#
if __name__ == "__main__":
    register_and_run()
