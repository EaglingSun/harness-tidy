# CHANGELOG

## 1.4.0
- inventory: `/skill-doctor` 사용 데이터(사용 횟수 · 마지막 사용 · 컨텍스트 비용)를 skill-usage.txt 로 저장해 Top 3 근거로 쓴다. 로드됐지만 안 쓴 skill 은 정리 대상이 아니라 「끄기 후보」로 따로 적는다. 실행할 수 없으면 「사용 데이터 없음」. Windows Git Bash 는 `MSYS_NO_PATHCONV=1` 이 있어야 `/skill-doctor` 가 경로로 바뀌지 않는다(실행 확인)
- 정리 모드 공통: 사용자가 `/doctor prompt-audit {대상}` 을 돌렸으면 지적을 1단계 검토 문서 [확인필요]로 받는다. harness-tidy 기준과 어긋나면 둘 다 적어 묻는다. HT-12 에 「공식 점검 결과는 다시 만들지 않고 1단계 입력으로 받는다」 한 구절
- claude-md 넘김: 내장 `/doctor`(Check 2~4)를 먼저 쓰고 claude-md-improver 는 설치된 경우 선택으로. handoff.md 에 `/doctor` 는 모델이 부를 수 없다는 점 · `/skill-doctor` 안내 추가
- 공식 대응: 있음 — 미사용 판정은 `/skill-doctor` · `/doctor` Check 1, CLAUDE.md 다듬기는 `/doctor` Check 3 · 4, 구식 · 모순은 `/doctor prompt-audit`. 이 판은 그 결과를 읽어 쓰는 단계만 넣고 판정 기능은 새로 만들지 않았다
- 스크립트 · 시험은 1.3.1 과 같다

## 1.3.1
- triage(HT-20): 스크립트의 `충돌?` 힌트를 없앴다. 유사도 + 부정어 유무로 정한 충돌 힌트는 실제 하네스에서 오탐이 많았고, 같은 일을 `/doctor prompt-audit`(Group 2 지시 파일 간 모순)이 override · 신구 판정까지 넣어 한다. 극성이 다른 쌍은 이제 힌트를 달지 않는다(`중복?` 으로 바꿔 부르지 않는다)
- 공식 대응: 있음 — 충돌 판정은 `/doctor prompt-audit` 결과를 triage 표의 `충돌` 태그로 옮긴다(modes.md triage 1-1). 못 쓰면 요약에 「충돌 점검 안 함」
- prompt-audit 넘김 안내에 범위를 적었다: 프로젝트 `/doctor prompt-audit` · 전역 `/doctor prompt-audit ~/.claude`(경로를 줘야 전역이 범위에 든다) — handoff.md · modes.md inventory
- 바뀐 것: inventory.py `rules_triage()` · triage 표 머리말 · summary.md triage 요약 · SKILL.md HT-20 한 구절 · tests/test_rules.py(충돌 시험을 「충돌? 없음 · 같은 극성은 중복? · 다른 극성은 중복? 아님 · 머리말에 충돌? 없음」 4건으로 교체). `중복?` 의 행당 상위 3칸에서 충돌 쌍이 빠지므로 `중복?` 행 수는 1.3.0 보다 늘 수 있다. 그 밖의 모드 · 규칙은 1.3.0 과 같다

## 1.3.0
- HT-20 추가 · modes.md 에 triage 모드(규칙 전수 표): `inventory.py --rules` 가 하네스 전체를 규칙 한 줄 = 1행(R001…)으로 뽑고 힌트(중복? · 충돌? · 일회성? · 모호 · 용어)를 단다. 태그(기준 · 일회성 · 중복 · 충돌 · 모호)와 결정(유지 · 수정 · 묶음 · 이동 · 뺄)을 받고 `--triage-check` exit 0 뒤 대상별 모드로 넘긴다. 대상별 검토 문서 결정 칸은 triage 결정으로 미리 채운다
- HT-21 추가 · templates/cold-read.md: 2단계 정리본을 정리 맥락 없는 서브에이전트에 주고 (judge) 규칙마다 해석 · 경계 사례를 받아 원문 · why 와 대조. 어긋남 · 모호 0 일 때만 넘긴다
- HT-22 추가 · templates/glossary.md: 용어집(.claude/glossary.md → ~/.claude/glossary.md)을 따르고 `inventory.py --terms` exit 0 일 때만 넘긴다
- HT-07 변경: 예외도 (예외: …) 또는 why.md#{ID} 로 보존. templates/rule-format.md 에 예외 · 용어 절, 금지어에 「필요하면」 · 「알아서」 추가
- SKILL.md 본문 40줄 유지: Input 두 줄 · Output 두 줄을 각각 한 줄로 묶음 (규칙 내용 변경 없음)
- summary.md 에 triage 요약 · 2단계 요약에 용어 · 콜드 줄, handoff.md 점검 목록에 콜드 리드 · 용어 추가
- tests/test_rules.py 추가. 기존 HT-01~19 · --coverage 동작은 1.2.0 과 같다

## 1.2.0
- HT-19 추가 · modes.md 에 add 모드(새 기준·규칙 추가): 인벤토리 → placement 배치 판정 → 중복·충돌 확인 → 제안 → 승인 뒤 반영. 「기준 추가해줘」 · 「규칙 추가해줘」 트리거가 이 절차로 이어진다
- HT-05 변경: 「정리 중」 임의 추가 금지로 좁히고, 사용자가 요청한 신규 규칙은 add 모드(HT-19)로 다룬다
- placement.md: 전역(~/.claude/) · 프로젝트(.claude/) 범위 판정 줄 추가
- 스크립트 · 템플릿 · 기존 규칙 HT-01~04 · 06~18 은 1.1.1 과 같다. add 모드는 매핑표 · --coverage 를 쓰지 않는다

## 1.1.1
- SKILL.md description: 「기준 추가」 · 「규칙 추가」 · 「기준 문서화」 · 「규칙 문서화」 · 「이 규칙 어디에 넣지」 · 「CLAUDE.md 에 규칙 추가」 트리거 추가. 정리 요청이 아니어도 하네스 파일에 규칙을 새로 넣을 때 스킬이 호출된다. 규칙(HT-01~18) · 모드 · 템플릿 · 스크립트는 1.1.0 과 같다

## 1.1.0
- HT-07 변경: 규칙 = 행동을 지시 · 금지하는 문장. Rules 절 밖(Procedure · Output · Don't)과 procedure.md · pitfalls.md 로 옮긴 규칙에도 ID 를 붙이고, 옮겨도 ID 는 그대로 둔다
- templates/mapping.md: 이동 예시가 새 ID 를 `—` 로 비우던 것을 고침. 새 ID 칸은 ID 또는 `없음(사유: …)` (빈칸 · `—` 금지), 변경 유형은 다섯 가지만
- inventory.py --coverage: 새 ID 없는 행(「ID 없음」)과 다섯 가지 밖 변경 유형(「유형 오류」)을 표시하고 exit 1. 1.0.0 매핑표의 `—` 행은 이제 실패로 나온다 → `없음(사유: …)` 나 ID 로 고친다
- HT-10: --coverage 가 exit 0 일 때만 넘긴다 · 2단계 요약에 ID 줄 추가 · tests/test_coverage.py 추가

## 1.0.0
- 첫 공개판. 규칙(HT-01~18) · 모드 · 템플릿은 1.0.0-rc.2 와 같다. 이후 1.0.x 는 문서 오타만 고친다
- MIT 라이선스 추가
- inventory.py: `--file` 상대 경로를 `--root` 기준으로 푼다 · 프로젝트 상위 폴더 이름이 build 등이어도 목록에서 빠지지 않는다 · `--coverage` 는 mapping.md 의 첫 표만 읽는다
- 문서: 설치 안내를 저장소 받기 기준으로 · skill-creator 설치 명령과 hook 문구를 공식 문서에 맞춤

## 1.0.0-rc.2
- HT-10 변경: Eval 씨앗을 정리본이 아니라 mapping.md 전체 행에서 만든다 → 빼거나 옮긴 규칙의 회귀도 원본·정리본 비교에서 잡힌다
- templates/mapping.md: 행 번호(Mxx) · Eval 케이스 칸 추가 (빈칸 금지, 없으면 사유)
- templates/evals.json: expected_output 에 [규칙 ID][매핑 행], 이동 · 뺄 케이스 예시
- inventory.py --coverage evals/{대상}: 매핑 행 대비 케이스 커버리지 확인
- handoff: 원본·정리본 같은 케이스 세트, 이동 케이스는 rule 로드 경로를 만질 것, 넘기기 전 커버리지 100%

## 1.0.0-rc.1
- 모드: inventory · skill · agent · prompt(그 밖의 지시 파일) · claude-md · rules · style · memory
- HT-17 단계별 화면 요약 20줄 이내 (templates/summary.md)
- HT-18 매핑표 고정 위치 evals/{대상}/mapping.md + 변경 유형 (templates/mapping.md)
- Windows 대응: 줄 수는 inventory.py --file, 줄 번호는 Grep 도구 (wc -l · grep -n 의존 제거), .bak 확장자 규칙
- inventory.py: --extra (표준 위치 밖 지시 파일) · --file (단일 파일 줄 수) · --version
- VERSION · CHANGELOG 추가
