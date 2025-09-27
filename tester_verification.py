#!/usr/bin/env python3
"""
테스터 독립 검증 스크립트
SSH 접속 후 이 파일을 실행하여 VModel AI 성능을 독립적으로 검증
"""

import json
import os
from datetime import datetime

def calculate_ktcc_metrics():
    """KTCC 기준에 따른 성능 지표 계산"""
    
    print("🔍 VModel AI 성능 지표 독립 검증 시작...")
    
    # 성능 로그 파일 읽기
    performance_data = []
    try:
        with open("performance_data/performance_log.jsonl", "r", encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    performance_data.append(json.loads(line))
    except FileNotFoundError:
        print("❌ 성능 데이터 파일을 찾을 수 없습니다.")
        return
    
    if not performance_data:
        print("❌ 성능 데이터가 없습니다.")
        return
    
    # 기본 통계
    total_tests = len(performance_data)
    successful_tests = sum(1 for record in performance_data if record['success'])
    completed_tests = sum(1 for record in performance_data if record['completed'])
    
    # KTCC 기준 계산
    accuracy = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
    precision = (completed_tests / successful_tests) * 100 if successful_tests > 0 else 0
    recall = (completed_tests / total_tests) * 100 if total_tests > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    # 처리 시간 분석
    processing_times = [record['total_time'] for record in performance_data if record['success']]
    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
    
    # 결과 출력
    print("\n" + "="*60)
    print("📊 KTCC 성능 기준 검증 결과")
    print("="*60)
    print(f"📈 총 테스트 수: {total_tests}")
    print(f"✅ 성공한 테스트: {successful_tests}")
    print(f"🎯 완료된 테스트: {completed_tests}")
    print()
    print("🏆 성능 지표 (75% 기준):")
    print(f"   📊 Accuracy: {accuracy:.1f}% {'✅' if accuracy >= 75 else '❌'}")
    print(f"   🎯 Precision: {precision:.1f}% {'✅' if precision >= 75 else '❌'}")
    print(f"   📈 Recall: {recall:.1f}% {'✅' if recall >= 75 else '❌'}")
    print(f"   🏅 F1-Score: {f1_score:.1f}% {'✅' if f1_score >= 75 else '❌'}")
    print()
    print("⏱️ 처리 시간 (60초 기준):")
    print(f"   평균 처리 시간: {avg_processing_time:.1f}초 {'✅' if avg_processing_time <= 60 else '❌'}")
    print()
    
    # 전체 기준 통과 여부
    all_passed = (accuracy >= 75 and precision >= 75 and 
                 recall >= 75 and f1_score >= 75 and 
                 avg_processing_time <= 60)
    
    print("🎯 최종 결과:")
    if all_passed:
        print("   🏆 모든 KTCC 기준을 통과했습니다!")
    else:
        print("   ❌ 일부 기준을 통과하지 못했습니다.")
    
    print("="*60)
    
    return {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1_score': f1_score,
        'avg_processing_time': avg_processing_time,
        'all_passed': all_passed
    }

def show_raw_logs():
    """원본 로그 파일 표시"""
    print("\n📄 VModel API 원본 로그:")
    print("-" * 40)
    
    try:
        with open("logs/vmodel_api_raw.log", "r", encoding='utf-8') as f:
            content = f.read()
            print(content[-2000:])  # 마지막 2000자만 표시
    except FileNotFoundError:
        print("❌ 로그 파일을 찾을 수 없습니다.")

def show_success_summary():
    """성공/실패 요약 표시"""
    print("\n📊 성공/실패 요약:")
    print("-" * 40)
    
    try:
        with open("logs/success_failures.log", "r", encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-10:]:  # 마지막 10개 결과만 표시
                print(line.strip())
    except FileNotFoundError:
        print("❌ 요약 로그를 찾을 수 없습니다.")

if __name__ == "__main__":
    import sys
    
    print("🔧 VModel AI 테스터 독립 검증 도구")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--metrics":
            calculate_ktcc_metrics()
        elif sys.argv[1] == "--logs":
            show_raw_logs()
        elif sys.argv[1] == "--summary":
            show_success_summary()
        else:
            print("사용법: python tester_verification.py [--metrics|--logs|--summary]")
    else:
        # 전체 검증 실행
        calculate_ktcc_metrics()
        print("\n" + "="*60)
        show_success_summary()
