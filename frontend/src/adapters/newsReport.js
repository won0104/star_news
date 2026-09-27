const SOURCE_LIMIT = 5
const TOP_TOPIC_LIMIT = 3

export function reportFromApi(payload) {
  const sourceRows = sourceReads(payload?.sourceReads ?? [])
  const weeks = weeklyTrend(payload?.weeklyTopicTrend ?? [])
  const terrainNodes = payload?.topicLandscape ?? []

  return {
    title: '최근 3개월의 뉴스 리포트',
    eyebrow: generatedLabel(payload?.generatedAt),
    summary: summaryParts(payload, sourceRows.length),
    sources: {
      label: '출처별 읽기 비중',
      rows: sourceRows,
      footnote: sourceFootnote(sourceRows),
    },
    weeks,
    terrain: {
      label: '최근 주제 지형',
      hint: '내가 읽은 정도와 전체 독자의 관심도를 함께 보여줘요.',
      quadrants: {
        topLeft: '전체에서 주목한 흐름',
        topRight: '함께 자주 본 흐름',
        bottomLeft: '가볍게 접한 흐름',
        bottomRight: '나에게 익숙한 흐름',
      },
      clusters: terrainClusters(terrainNodes),
      axisX: '가로축 · 내가 읽은 정도',
      axisY: '세로축 · 전체 독자가 읽은 정도',
    },
  }
}

/**
 * 같은 자리에 선 노드를 하나로 묶는다.
 *
 * 겹침은 흔들림이 아니라 정확한 동점이다. 서버가 x 를 읽은 기사 수의 min-max 정규화로
 * 잡는데(NewsReportService.normalizeLogCount), 그 수가 작은 정수라 서로 다른 값이 몇 개
 * 안 나온다. 기사를 하나씩만 읽은 사용자는 `maxLog == minLog` 에 걸려 열두 노드가 전부
 * 한가운데 0.5 로 떨어진다.
 *
 * 그래서 흩뜨리지 않고 묶는다. 옮겨 놓으면 같은 수를 읽은 것을 다르게 읽은 것처럼 말하게
 * 되는데, 축 이름이 그대로 "내가 읽은 정도"다.
 *
 * 좌표는 서버가 이미 소수 첫째 자리로 반올림해 보내므로 문자열로 묶어도 안전하다.
 */
function terrainClusters(nodes) {
  const byPosition = new Map()

  nodes.forEach((node) => {
    const at = `${node.x}:${node.y}`
    const found = byPosition.get(at)
    const member = { id: node.nodeKey, label: node.label, familiarity: node.familiarity }
    if (found) {
      found.members.push(member)
      // 한 자리에 약한 것과 강한 것이 섞이면 강한 쪽으로 그린다. 묶은 점 하나가 그중
      // 가장 짙은 것을 대표한다.
      found.strong = found.strong || node.strong
      return
    }
    byPosition.set(at, { id: at, x: node.x, y: node.y, strong: node.strong, members: [member] })
  })

  return [...byPosition.values()]
}

function sourceReads(reads) {
  const sorted = [...reads].sort((left, right) => right.readArticleCount - left.readArticleCount)
  if (sorted.length <= SOURCE_LIMIT) {
    return sorted.map((row) => ({
      id: String(row.organizationId),
      label: row.organizationName,
      share: row.ratio,
    }))
  }

  const head = sorted.slice(0, SOURCE_LIMIT - 1)
  const rest = sorted.slice(SOURCE_LIMIT - 1)
  return [
    ...head.map((row) => ({
      id: String(row.organizationId),
      label: row.organizationName,
      share: row.ratio,
    })),
    {
      id: 'other',
      label: '기타',
      share: roundOne(rest.reduce((sum, row) => sum + row.ratio, 0)),
    },
  ]
}

function weeklyTrend(weeks) {
  const totals = new Map()
  const labels = new Map()

  weeks.forEach((week) => {
    ;(week.topics ?? []).forEach((topic) => {
      totals.set(topic.topicCode, (totals.get(topic.topicCode) ?? 0) + topic.readArticleCount)
      labels.set(topic.topicCode, topic.topicName)
    })
  })

  // 서버는 열람이 0건인 분야도 12주 내내 0으로 채워 내려준다(DTO 계약). 그 0들을 그대로
  // 줄 세우면 동점이 코드순으로 갈려, 읽지도 않은 분야가 상위 세 칸을 채우러 올라온다.
  // 한 건이라도 읽은 분야만 후보로 둔다.
  const rankedCodes = [...totals.keys()]
    .filter((code) => (totals.get(code) ?? 0) > 0)
    .sort((left, right) => {
      const difference = (totals.get(right) ?? 0) - (totals.get(left) ?? 0)
      return difference || left.localeCompare(right)
    })
  const topCodes = rankedCodes.slice(0, TOP_TOPIC_LIMIT)
  const topSet = new Set(topCodes)
  // 접어 넣을 게 남았을 때만 기타를 세운다. 언제나 0인 기타 칸은 범례만 차지한다.
  const hasOther = rankedCodes.length > topCodes.length
  const series = [
    ...topCodes.map((code) => ({ id: code, label: labels.get(code) ?? code })),
    ...(hasOther ? [{ id: 'OTHER', label: '기타' }] : []),
  ]

  const columns = weeks.map((week, index) => {
    const byCode = new Map(
      (week.topics ?? []).map((topic) => [topic.topicCode, topic.readArticleCount]),
    )
    const folded = [...byCode.entries()].filter(([code]) => !topSet.has(code))
    const other = folded.reduce((sum, [, count]) => sum + count, 0)

    return {
      month: monthLabel(week.weekStart, index === 0 ? null : weeks[index - 1]?.weekStart),
      weekStart: week.weekStart,
      // series 와 언제나 같은 길이. 기타를 세우지 않았으면 그 칸도 없다.
      values: [...topCodes.map((code) => byCode.get(code) ?? 0), ...(hasOther ? [other] : [])],
      /*
       * 이 주의 기타에 무엇이 들었는지. 조각에 마우스를 올렸을 때 그 자리에서 답하려고
       * 남긴다 — 묻는 것이 "이 주의 기타"이므로 12주 합계로 답하면 딴 말이 된다.
       *
       * 0인 분야는 뺀다. 기타에 접히는 것은 대부분 0이라 그대로 두면 목록이 0으로 채워져
       * 정작 읽은 분야가 묻힌다. rankedCodes 순서를 따라 많이 읽은 것부터 세운다.
       */
      otherParts: hasOther
        ? rankedCodes
          .slice(TOP_TOPIC_LIMIT)
          .map((code) => ({ id: code, label: labels.get(code) ?? code, count: byCode.get(code) ?? 0 }))
          .filter((part) => part.count > 0)
        : [],
    }
  })

  const highestWeek = Math.max(
    0,
    ...columns.map((column) => column.values.reduce((sum, value) => sum + value, 0)),
  )
  const axisMax = Math.max(5, Math.ceil(highestWeek / 5) * 5)
  const halfway = Math.ceil(axisMax / 2)

  return {
    label: '최근 12주의 분야별 읽기 변화',
    hint: '주별 최초 열람 기사 수와 분야 구성을 보여줘요.',
    insights: weeklyInsights(weeks, labels),
    // 출처 블록의 각주와 같은 역할 — 비어 있는 이유를 빈칸 대신 말로 적는다.
    empty: series.length === 0 ? '아직 주별로 쌓인 기록이 없어요.' : null,
    series,
    axisMax,
    ticks: halfway === axisMax ? [axisMax] : [halfway, axisMax],
    columns,
  }
}

/*
 * 차트 아래 해석 한두 줄. 숫자에서 바로 나오는 것만 말한다 — 추측이나 평가는 붙이지 않는다.
 *
 * ① 12주 동안 가장 많이 읽은 분야와 그 비중.
 * ② 최근 4주가 그 앞 4주보다 가장 많이 늘어난 분야. 늘어난 분야가 없으면 이 줄은 없다.
 *    4주는 "지난달"에 가까운 잠정 구간이다.
 */
const RECENT_WEEKS = 4

function weeklyInsights(weeks, labels) {
  const sumBy = (range) => {
    const sums = new Map()
    range.forEach((week) =>
      (week.topics ?? []).forEach((topic) =>
        sums.set(topic.topicCode, (sums.get(topic.topicCode) ?? 0) + topic.readArticleCount),
      ),
    )
    return sums
  }

  const all = sumBy(weeks)
  const total = [...all.values()].reduce((sum, value) => sum + value, 0)
  if (total === 0) return []

  const [topCode, topCount] = [...all.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]
  const topName = labels.get(topCode) ?? topCode
  // 줄마다 조각 목록이다. 데이터에서 나온 수만 `strong` 으로 표시해 화면이 굵게 그린다.
  const lines = [
    [
      { text: `이번 기간엔 ${withObject(topName)} 가장 많이 읽었어요. 전체의 ` },
      { text: `${Math.round((topCount / total) * 100)}%`, strong: true },
      { text: '예요.' },
    ],
  ]

  const recent = sumBy(weeks.slice(-RECENT_WEEKS))
  const before = sumBy(weeks.slice(-RECENT_WEEKS * 2, -RECENT_WEEKS))
  const grown = [...recent.entries()]
    .map(([code, count]) => [code, count - (before.get(code) ?? 0)])
    .filter(([, diff]) => diff > 0)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]
  if (grown) {
    lines.push([
      {
        text: `최근 ${RECENT_WEEKS}주에는 ${labels.get(grown[0]) ?? grown[0]} 읽기가 그 전 ${RECENT_WEEKS}주보다 `,
      },
      { text: String(grown[1]), strong: true },
      { text: '건 늘었어요.' },
    ])
  }
  return lines
}

/** 받침에 따라 을/를. 한글로 끝나지 않으면 둘 다 적는다. */
function withObject(word) {
  const code = word.charCodeAt(word.length - 1) - 0xac00
  if (code < 0 || code > 11171) return `${word}을(를)`
  return `${word}${code % 28 === 0 ? '를' : '을'}`
}

function monthLabel(current, previous) {
  const month = /^\d{4}-(\d{2})/.exec(current ?? '')?.[1]
  const previousMonth = /^\d{4}-(\d{2})/.exec(previous ?? '')?.[1]
  if (!month || month === previousMonth) return ''
  return `${Number(month)}월`
}

/*
 * 쪽 머리의 요약 한 문장. 예전에는 같은 수를 아래 요약 밴드(읽은 기사 28 · 접한 출처 16)에서
 * 한 번 더 세웠는데, 한 쪽에서 같은 말을 두 번 했다. 문장만 남기고 숫자만 강조한다 — 강조할
 * 조각은 `strong: true` 로 표시해 화면이 굵게 그린다.
 */
function summaryParts(payload, displayedSourceCount) {
  const count = payload?.totalReadArticleCount ?? 0
  const sourceCount = payload?.sourceReads?.length ?? displayedSourceCount
  const period = payload?.period
  // 기간의 두 날짜도 데이터에서 온 값이라 숫자와 같이 강조한다.
  const range = period?.from && period?.to
    ? [
      { text: formatDate(period.from), strong: true },
      { text: '부터 ' },
      { text: formatDate(period.to), strong: true },
      { text: '까지 ' },
    ]
    : [{ text: '최근 3개월 동안 ' }]
  return [
    ...range,
    { text: String(count), strong: true },
    { text: '개의 기사에서 ' },
    { text: String(sourceCount), strong: true },
    { text: '개 출처를 접했어요.' },
  ]
}

function generatedLabel(value) {
  return value ? `MY READING CHART · ${formatDate(value)} 생성` : 'MY READING CHART'
}

function sourceFootnote(rows) {
  if (rows.length === 0) return '아직 집계할 기사 열람 기록이 없어요.'
  const top = rows.slice(0, 2)
  const share = roundOne(top.reduce((sum, row) => sum + row.share, 0))
  return `${top.map((row) => row.label).join('·')} 비중이 전체 읽기 기록의 ${share}%예요.`
}

function formatDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value ?? '')
  if (!match) return value ?? ''
  const [, year, month, day] = match
  return `${year}년 ${Number(month)}월 ${Number(day)}일`
}

function roundOne(value) {
  return Math.round(value * 10) / 10
}
