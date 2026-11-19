# why.md — harness-tidy 규칙의 근거

공식 `/doctor prompt-audit` 처방과 방향이 달랐던 harness-tidy 규칙의 근거를 적는다 (CONTRIBUTING.md HTD-04). 1.5.0 에서 바꾼 규칙 다섯 개만 다룬다.

- 공식 원문: Claude Code 2.1.326 에 들어 있는 prompt-audit 지침에서 짧게 인용하고, 항목 이름은 지침 표기를 따른다
- harness-tidy 근거: 개인 하네스 한 곳에 prompt-audit 을 한 번 돌린 결과(지적 138건)를 코드로 집계한 건수다. 지적의 「패턴」 칸에 그 패턴 이름이 있으면 센다. 하네스 한 곳 · 1회 실측이라 다른 하네스에서도 같은 비율이 나온다는 근거는 아니다

## HT-07
- 공식 원문: Group 2 「History narratives: past tense, incident IDs, PR numbers, pinned model names」 → 「State the current rule; drop the archaeology」 (지금 규칙만 쓰고, 그 규칙이 생긴 경위는 덜어 낸다)
- harness-tidy 근거: 지적 138건 중 「패턴」 칸에 History narratives 가 있는 지적 20건, 그중 첫 패턴인 지적 14건. 1.4.0 HT-07 은 이유를 보존하라고 했지만 경위(날짜 · 회차 · 건수)를 이유와 나누지 않았다
- 1.5.0 처리: 경위는 why.md#{ID} 출처 칸으로 옮기고, 규칙 줄에는 지금 지킬 행동과 이유만 둔다 (SKILL.md HT-07 · templates/rule-format.md · templates/why.md). triage 에서 날짜가 경위 꼬리표일 뿐인 규칙은 일회성이 아니라 기준으로 본다 (modes.md triage 2)

## HT-09
- 공식 원문: keep list 2 「Cruft != length. … Never justify a deletion by character count alone.」 (길이만으로 삭제를 정당화하지 않는다)
- harness-tidy 근거: 1.4.0 HT-09 는 본문 줄 수가 상한을 넘으면 줄이라고 했다. 같은 실측에서 「패턴」 칸에 길이를 든 지적은 0건이고, 이유를 지우라는 지적도 0건이다(「reason」이 들어간 2건은 절대 규칙에 이유를 붙이라는 1d 지적)
- 1.5.0 처리: 줄 수는 참고 기준으로 표시만 한다 — inventory.py flag 「줄 수 참고(n>기준)」, 검토 문서 · 화면 요약의 「참고 기준」. 줄 수만으로 빼거나 줄이지 않는다. 기준 값(skill·agent·prompt 40 · CLAUDE.md 50 · rule 30)과 exit 코드는 그대로다

## HT-15
- 공식 원문: keep list 8 「Working redundancy is not cruft. … propose deduplication or consolidation only when the duplicates actually disagree」 (작동하는 중복은 정리 대상이 아니다. 서로 어긋날 때만 합치자고 제안한다)
- harness-tidy 근거: 1.4.0 HT-15 는 같은 맥락에서 자동 로드되는 곳에 이미 있으면 빼라고 해서, 어긋나지 않는 중복도 뺄 후보가 됐다. 어긋나지 않는 중복을 빼서 결과가 나아졌다는 harness-tidy 실측은 없다
- 1.5.0 처리: 어긋나지 않고 작동하는 중복은 결정 칸에 `유지?` 로 제안하고 묻는다. 빼거나 묶는 처리는 prompt-audit Group 2 가 어긋남을 짚었거나 사용자가 묶기로 정했을 때만 한다 (SKILL.md HT-15 · placement.md 「중복을 발견했을 때」 · modes.md triage 2 · agent 3 · 4 · templates/summary.md)

## HT-17
- 공식 원문: 1f Output-shaping choreography 「numeric output ceilings ("under 120 words", "at most five bullets") … re-express the goal as audience/outcome framing without the number」 (숫자 출력 상한은 빼고 목적으로 다시 쓴다) · keep list 7 「Format-pinning examples on genuinely format-sensitive outputs stay」 (형식이 중요한 출력의 형식 예시는 남긴다)
- harness-tidy 근거: 같은 실측에서 harness-tidy 1.2.0 SKILL.md 의 HT-17 「단계마다 20줄 이내」와 templates/summary.md 제목이 1f 로 지적됐다(1건). summary.md 의 「결정 필요가 10건을 넘으면 상위 10건만」은 지적되지 않았다 — triage 표가 수백 행일 때 화면을 막는 표시 형식이다
- 1.5.0 처리: 「20줄 이내」를 빼고 「templates/summary.md 형식의 요약」으로 바꿨다. summary.md 의 「10건」 표시 형식은 그대로 둔다

## description
- 공식 원문: Group 2 「Trigger-case enumeration: description lists of near-synonymous example queries, growing one phrase per missed trigger」 → 「Name generalized categories of intent」 (비슷한 예시 문구를 늘어놓지 말고 요청의 의도 범주를 쓴다)
- harness-tidy 근거: 같은 실측에서 harness-tidy 1.2.0 description(요청 문구 14개)이 Trigger-case enumeration 으로 지적됐다(1건). 1.4.0 은 triage 문구 3개를 더해 17개였고, modes.md skill 모드도 「요청 표현 3개 이상」을 가르쳤다
- 1.5.0 처리: description 은 하는 일 + 요청의 의도 범주(예시 두세 개) + 이웃 스킬 경계로 쓴다. 바꾼 문구는 trigger eval 로 호출률이 1.4.0 보다 떨어지지 않는 것을 확인한 뒤에 넣는다
