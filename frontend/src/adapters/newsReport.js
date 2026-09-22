const SOURCE_LIMIT = 5
const TOP_TOPIC_LIMIT = 3

export function reportFromApi(payload) {
  const sourceRows = sourceReads(payload?.sourceReads ?? [])
  const weeks = weeklyTrend(payload?.weeklyTopicTrend ?? [])
  const terrainNodes = payload?.topicLandscape ?? []

  return {
    title: '최근 3개월의 뉴스 리포트',
    eyebrow: generatedLabel(payload?.generatedAt),
    summary: summaryText(payload, sourceRows.length),
    totals: [
      { id: 'articles', label: '읽은 기사', value: payload?.totalReadArticleCount ?? 0 },
      { id: 'topics', label: '주제 지형 노드', value: terrainNodes.length },
      { id: 'sources', label: '접한 출처', value: payload?.sourceReads?.length ?? 0 },
    ],
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
    const other = [...byCode.entries()]
      .filter(([code]) => !topSet.has(code))
      .reduce((sum, [, count]) => sum + count, 0)

    return {
      month: monthLabel(week.weekStart, index === 0 ? null : weeks[index - 1]?.weekStart),
      // series 와 언제나 같은 길이. 기타를 세우지 않았으면 그 칸도 없다.
      values: [...topCodes.map((code) => byCode.get(code) ?? 0), ...(hasOther ? [other] : [])],
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
    // 출처 블록의 각주와 같은 역할 — 비어 있는 이유를 빈칸 대신 말로 적는다.
    empty: series.length === 0 ? '아직 주별로 쌓인 기록이 없어요.' : null,
    series,
    axisMax,
    ticks: halfway === axisMax ? [axisMax] : [halfway, axisMax],
    columns,
  }
}

function monthLabel(current, previous) {
  const month = /^\d{4}-(\d{2})/.exec(current ?? '')?.[1]
  const previousMonth = /^\d{4}-(\d{2})/.exec(previous ?? '')?.[1]
  if (!month || month === previousMonth) return ''
  return `${Number(month)}월`
}

function summaryText(payload, displayedSourceCount) {
  const count = payload?.totalReadArticleCount ?? 0
  const sourceCount = payload?.sourceReads?.length ?? displayedSourceCount
  const period = payload?.period
  const range = period?.from && period?.to
    ? `${formatDate(period.from)}부터 ${formatDate(period.to)}까지`
    : '최근 3개월 동안'
  return `${range} ${count}개의 기사에서 ${sourceCount}개 출처를 접했어요.`
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
