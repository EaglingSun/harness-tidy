# Modes

inventory · triage 를 뺀 정리 모드는 1단계(검토 문서) → 결정 → 2단계(정리본) → 콜드 리드(HT-21) · 용어 lint(HT-22) → 3단계(handoff, 승인 시) 순서다.
- 콜드 리드: templates/cold-read.md 대로 정리본만 서브에이전트에 준다. 결과는 evals/{대상}/cold-read.md. 어긋남 · 모호는 검토 문서 [확인필요]로 되돌려 결정을 받고 정리본을 고친 뒤 다시 돌린다
- 용어 lint: `python scripts/inventory.py --terms {정리본}` exit 0. 위반은 표준어로 고치고, 표준어가 없으면 용어집 추가안을 [확인필요]로 낸다
- (선택) 공식 점검 입력: 사용자가 1단계 전에 `/doctor prompt-audit {대상 경로}` 를 돌렸으면 지적을 검토 문서 [확인필요]로 옮긴다 (handoff.md 결과 받기). 지적이 harness-tidy 기준(줄 수 상한 · 한 곳 · 한 줄 명령형)과 어긋나면 한쪽을 고르지 말고 둘 다 적어 묻는다

## Mode: inventory (대상이 없을 때, "하네스 정리" · "하네스 인벤토리")
비용 단계: L0 목록(스크립트, 기본) → L1 대상 주변(대상 정리 때) → L2 전체 의미 비교(요청·정기 점검 때만)
0. 먼저 `python scripts/inventory.py --out docs/reports/{날짜}-harness-tidy/inventory.md` 를 돌린다 (--include-user · --memory · --changed-since {커밋} 선택). Claude 는 이 표를 읽고, 본문은 Top 3 판단에 필요한 파일만 연다
   - 사용 데이터: `/skill-doctor` 표를 `docs/reports/{날짜}-harness-tidy/skill-usage.txt` 로 저장한다. PowerShell `claude.cmd -p "/skill-doctor"` · Git Bash `MSYS_NO_PATHCONV=1 claude.cmd -p "/skill-doctor"`(빼면 `/skill-doctor` 가 경로로 바뀌어 실패) · macOS/Linux `claude -p "/skill-doctor"`. 실행할 수 없으면(기능 꺼짐 · 구버전) 결과에 「사용 데이터 없음」을 적는다
1. 스크립트가 찾는 위치 (사용자 ~/.claude/ 와 프로젝트 .claude/)
   - 지시 계층(정리 대상): CLAUDE.md · CLAUDE.local.md · 하위 폴더 CLAUDE.md · AGENTS.md · .claude/rules/ · .claude/skills/ · .claude/commands/ · .claude/agents/ · .claude/output-styles/ · auto memory(~/.claude/projects/{프로젝트}/memory/MEMORY.md)
   - 실행·설정 계층(목록만): settings.json 의 hooks · permissions · outputStyle · agent, .mcp.json, 설치된 plugins
2. 표 1행 = 파일 1개: 종류 · 경로 · 로드 조건(placement.md) · 줄 수 · 규칙 ID 유무 · 줄글 비율(상/중/하) · 트리거·위임 명확도(skill·agent) · 중복 후보
3. 공유 관계: 같은 규칙이 여러 파일에 있는 묶음과, 어떤 rule 을 어떤 skill·agent 가 쓰는지 (상류 → 하류)
4. 우선 정리 대상 Top 3 + 순서 (상류 먼저) + 선정 이유 1줄씩. skill 은 사용 횟수 · 마지막 사용 · 컨텍스트 비용(skill-usage.txt)도 근거로 쓴다. 로드됐지만 한 번도 안 쓴 skill 은 정리 대상이 아니라 「끄기 후보」로 따로 적는다 (끌지는 사용자가 `/skills` · `/doctor` 에서 정한다)
5. hook 전환 후보 (HT-16). L2(전체 의미 비교)는 사용자가 원할 때만 /doctor prompt-audit 또는 서브에이전트로 넘긴다 (handoff.md). prompt-audit 은 경로를 주지 않으면 프로젝트만 본다 — 전역까지 보려면 `/doctor prompt-audit ~/.claude` 를 따로 돌린다
6. 결과: docs/reports/{날짜}-harness-tidy/inventory.md. 어떤 대상 파일도 고치지 않는다
7. 다음 인벤토리는 `--changed-since {이번 커밋}` 으로 증분만 본다

## Mode: triage (규칙 전수 표 — "규칙 전수 정리" · "전역 규칙 정리" · "규칙이 너무 많아")
대상을 고르기 전에 규칙 전체를 한 표로 본다 (HT-20). 정리본을 만들지 않고, 어떤 파일도 고치지 않는다
1. `python scripts/inventory.py --rules --include-user --out docs/reports/{날짜}-harness-tidy/rules-triage.md` (프로젝트만이면 --include-user 빼기 · 증분은 --changed-since). 규칙 한 줄 = 1행(R001…), 힌트: 중복? · 일회성? · 모호 · 용어. 스크립트는 충돌 힌트를 달지 않는다
1-1. 충돌 점검은 공식 기능에 넘긴다: 사용자가 `/doctor prompt-audit`(프로젝트) · `/doctor prompt-audit ~/.claude`(전역 — 경로를 줘야 범위에 든다)를 돌리면, Group 2 지적(지시 파일 간 모순)을 해당 행의 태그 `충돌` 로 옮긴다. 돌리지 않았거나 쓸 수 없으면(v2.1.283 미만 · /claude-api 꺼짐) triage 요약에 「충돌 점검 안 함」을 적는다
2. Claude 가 행마다 태그 · 결정 제안을 채운다. 끝에 ? 를 붙인다 (예: `일회성?` · `뺄?`)
   - 기준: 지금도 지켜야 하는 판단 기준 → 대개 유지 · 수정
   - 일회성: 그때 한 번 한 지시가 굳은 것(날짜 · 특정 PR · 이번 작업) → 대개 뺄
   - 중복: 같은 뜻이 여러 곳 → 한 곳만 남기고 나머지는 묶음(비고: 남길 행) 또는 뺄 (HT-15, placement.md)
   - 충돌: 1-1 의 prompt-audit 지적으로만 붙인다. 사용자에게 어느 쪽인지 묻는다. 제안 없이 `충돌` · `수정?`
   - 모호: 판정 불가 표현 → 수정(비고: 고칠 방향). 규칙이 아닌 줄은 태그 `규칙 아님` · 결정 `유지`
3. 화면에는 templates/summary.md 의 triage 요약만 낸다 (HT-17): 충돌 → 일회성 → 중복 → 모호 순, 기준 · 유지는 개수만
4. 사용자 답("승인" 또는 "R014 유지, R020 뺄 …")으로 ? 를 지운다. `--triage-check` 가 exit 0 일 때까지 반복한다
5. 결정이 확정되면 파일별로 묶어 상류(CLAUDE.md · rule) → 하류(skill · agent) 순서 목록을 낸다. 대상별 모드 1단계 검토 문서의 결정 칸은 triage 결정으로 미리 채우고, 바뀐 것만 다시 묻는다 (HT-11 · 한 번에 한 대상)
6. triage 표의 줄 번호는 스크립트가 센 값이다. 검토 문서로 옮길 때 Grep 도구로 다시 확인한다 (HT-03)

## Mode: add (새 기준·규칙 추가 — "기준 추가해줘" · "규칙 추가해줘" · "이 규칙 어디에 넣지")
기존 파일을 정리하는 모드가 아니다. 사용자가 요청한 신규 규칙을 알맞은 자리에 넣는다 (HT-19). 정리 중 임의 추가 금지(HT-05)와 다르다
1. 규칙 원문을 사용자 표현 그대로 받는다. 대상 파일이 이미 정해져 있어도 3~5 를 거친다
2. `python scripts/inventory.py --near {후보 파일}` 로 주변 후보(L1)만 읽고, 같은 · 비슷한 규칙이 이미 있는지 찾는다 (HT-14). 전체 인벤토리는 대상 후보가 없을 때만 돌린다
3. placement.md 표로 둘 곳을 정한다. 범위는 전역 · 프로젝트로 나눈다: 여러 프로젝트가 공유하면 전역(~/.claude/), 한 프로젝트만 쓰면 프로젝트(.claude/). 레포 룰이 전역과 충돌하면 레포 룰이 이기므로 충돌을 먼저 적는다
4. 이미 같은 맥락에서 자동 로드되는 곳에 있으면 새로 넣지 않는다. 그 규칙 소관 파일과 줄을 알려 주고 보강할지 묻는다 (HT-15)
5. 제안을 낸다: 파일:줄 · 넣을 문안(HT-07 형식: ID 한 줄 명령형 · 이유 · 예외 · lint/judge, 용어는 용어집 HT-22) · 넣지 않고 hook 으로 갈 후보 여부(HT-16) · 줄 수 상한(HT-09) 초과 여부
6. 승인 뒤에만 고친다. 수정 전 {파일}.bak(HT-01). 반영 뒤 줄 수 · 상류(CLAUDE.md · rule)를 바꿨으면 하류 skill · agent 영향을 보고한다
7. 매핑표(evals/…/mapping.md)와 --coverage 는 만들지 않는다. 정리 전후 ID 대조용이다
8. 문안이 judge 규칙이면 콜드 리드(templates/cold-read.md)를 그 한 줄로 돌려 해석이 사용자 원문과 맞는지 확인한 뒤 승인을 받는다

## Mode: skill (.claude/skills/{이름}/SKILL.md · .claude/commands/{이름}.md)
1. 진단: 줄 수 · description 혼재 · ID 유무 · 다중 규칙 줄 · 중복 · lint 후보 · 바깥 중복(HT-14, `inventory.py --near {SKILL.md}`)
2. 결과 구조: SKILL.md / procedure.md / pitfalls.md / why.md / lint/forbidden.txt
3. description = 하는 일 1구절 + 실제 요청 표현 3개 이상 + 이웃 스킬 경계
4. 규칙마다 placement.md 로 자리를 정한다. rule 로 갈 규칙은 "rule 이동 후보"로 표시하고 그 rule 을 먼저 정리하자고 제안한다
5. 스킬이 경로 rule 에 기대면 Procedure 1 을 "대상 파일을 먼저 읽는다"로 둔다
6. commands/ 파일은 skills/{이름}/SKILL.md 로 옮기자고 제안한다 (같은 이름이면 skill 이 이긴다)
6-1. procedure.md · pitfalls.md 로 옮긴 규칙도 같은 ID 를 붙인다. Procedure · Output · Don't 의 지시 · 금지 문장도 규칙이다 (HT-07)
7. 결정 반영 → 정리본 · 매핑표 · 줄 수 · [확인필요] 보고 → handoff(skill-creator)

## Mode: agent (.claude/agents/{이름}.md)
1. 진단: description(위임 조건) 명확도 · tools 지정 여부(생략 = 전부 상속 → 최소 권한 점검) · model · 본문(system prompt)의 줄글 · Output(메인으로 돌려줄 요약 형식) 유무 · 바깥 중복
2. frontmatter 필드명은 정확히 쓴다 (오타는 조용히 무시된다)
3. 본문에 스킬 내용이 복사돼 있으면 `skills:` preload 로 바꾸자고 제안한다 (HT-15)
4. CLAUDE.md 는 에이전트에도 기본 로드된다(omitClaudeMd 제외) → CLAUDE.md 와 겹치는 규칙은 뺀다
5. 구조: templates/agent.md. Procedure · Output · Don't 의 지시 · 금지 문장도 ID 를 붙인다 (HT-07)
6. Eval: 위임 → trigger-eval.json (should_trigger = 자동 위임 여부) · 동작 → evals.json (prompt 에 `@"{이름} (agent)"` 로 명시 호출)
7. 결정 반영 → 정리본 · 매핑표 · 줄 수 → handoff(/doctor prompt-audit, Eval 실행)

## Mode: prompt (표준 위치 밖 지시 파일 — 예: harness/reviewer.md, CI 리뷰어 프롬프트)
1. agent 모드와 같이 다루되 frontmatter 점검(tools · model · skills)은 건너뛴다
2. 이 파일을 누가 읽는지 먼저 확인한다 (스크립트 · CI · 다른 지시 파일의 @참조 · "읽는다" 지시) → 검토 문서 맨 위에 적는다
3. 자동 로드되지 않으므로 같은 규칙이 CLAUDE.md · rule 에 있어도 빼지 않는다. 빼려면 이 파일을 읽는 쪽이 그 파일도 읽는지 확인한다
4. 인벤토리에 넣으려면 `inventory.py --extra "harness/**/*.md"`
5. Eval: 이 프롬프트를 쓰는 실행 경로(예: 리뷰어 CI)로 돌리고, 결과에 규칙 ID 를 남기게 한다 (evals/prompts/{파일명}/evals.json)

## Mode: claude-md (CLAUDE.md · CLAUDE.local.md · AGENTS.md)
1. 줄마다 분류: G 규칙 유지 / Skill Routing / rule 로 이동 / output style 로 이동 / docs·스킬로 이동 / hook 전환 후보 / 삭제 후보
2. 구조: templates/claude-md.md. 개인 설정은 CLAUDE.local.md, 팀 공유는 CLAUDE.md
3. 결정 반영 → 이동 내역 · 줄 수 보고 → handoff(내장 /doctor, 설치돼 있으면 claude-md-improver)
4. 정리본의 @ 참조 경로가 프로젝트에 없으면 이 스킬의 templates/ 에서 복사할지 묻는다

## Mode: rules (.claude/rules/*.md · ~/.claude/rules/*.md)
1. frontmatter `paths:` 는 그대로 둔다. 범위를 바꿔야 할 것 같으면 [확인필요]
2. 진단: 줄 수 · paths 범위 · 절차·도구 지시가 섞였는지(→ skill 이동 후보) · 중복
3. ID: {약어}-NN. 약어는 파일 이름에서 만들고 검토 문서에서 확인받는다
4. 하류 반영 표: `inventory.py --near {rule}` 의 후보(paths 겹침 · 표현 겹침) 중 skill·agent 를 읽고, 대상별로 "참조로 바꿀 규칙 ID"를 적는다
5. 결정 반영 → 정리본 · 매핑표 · 줄 수 · 하류 반영 표 보고
6. Eval: (judge) 씨앗은 evals/rules/{파일명}/evals.json, 실행은 이 rule 을 쓰는 대표 스킬의 Eval 에 포함해 넘긴다
7. 하류 대상 정리는 이 rule 이 확정된 뒤 따로 진행한다

## Mode: style (.claude/output-styles/*.md)
1. 응답의 역할 · 어조 · 형식만 남긴다. 프로젝트 사실은 CLAUDE.md, 작업 절차는 skill 로 이동 후보
2. `keep-coding-instructions` 를 의도대로 설정했는지 확인한다 (코딩 작업을 계속하면 true)
3. 결정 반영 → 정리본 · 이동 내역 보고

## Mode: memory (auto memory, MEMORY.md · 주제 파일)
1. 읽기 전용 검토다. 메모리 파일은 사용자 승인 없이 고치지 않는다
2. 반복되는 교정 · 규칙성 있는 항목을 찾아 placement.md 기준으로 승격 후보 표를 만든다 (CLAUDE.md · rule · skill · hook)
3. 이미 다른 하네스 파일에 있는 항목은 "중복" 으로 표시한다
4. MEMORY.md 가 200줄 · 25KB 한도에 가까운지 확인한다 (넘는 부분은 다음 세션에 로드되지 않는다)
5. 승격 승인 → 해당 대상 모드로 반영 → 메모리 항목 정리 여부를 사용자에게 묻는다
