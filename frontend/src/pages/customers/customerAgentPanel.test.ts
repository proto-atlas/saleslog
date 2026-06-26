import { describe, expect, test } from 'vitest'

import {
  buildApprovalPayload,
  buildPayloadDiffRows,
  getApprovalSubmitState,
  getBusinessRecordHref,
  hasPayloadChanges,
  isApprovalExpired,
  parseSseEventKeys,
  parseSseEvents,
  safeMessageLabel,
  stringifyJsonValue,
  validateApprovalPayload,
} from './customerAgentPanelHelpers'

describe('parseSseEventKeys', () => {
  test('SSE data行からsafe_message_keyだけを取り出す', () => {
    const text = [
      'id: 1',
      'event: run_created',
      'data: {"safe_message_key":"run_created"}',
      '',
      'id: 2',
      'event: completed',
      'data: {"safe_message_key":"completed"}',
      '',
    ].join('\n')

    expect(parseSseEventKeys(text)).toEqual(['run_created', 'completed'])
  })
})

describe('parseSseEvents', () => {
  test('SSEのidとevent名を保持する', () => {
    const text = [
      'id: 10',
      'event: citation_verified',
      'data: {"safe_message_key":"citation_verified"}',
      '',
    ].join('\n')

    expect(parseSseEvents(text)).toEqual([
      {
        eventSeq: 10,
        eventType: 'citation_verified',
        safeMessageKey: 'citation_verified',
      },
    ])
  })

  test('壊れたdata行は結果から除外する', () => {
    const text = [
      'id: 1',
      'event: run_created',
      'data: {',
      '',
      'id: 2',
      'event: completed',
      'data: {"safe_message_key":"completed"}',
      '',
    ].join('\n')

    expect(parseSseEvents(text)).toEqual([
      {
        eventSeq: 2,
        eventType: 'completed',
        safeMessageKey: 'completed',
      },
    ])
  })
})

describe('safeMessageLabel', () => {
  test('既知のsafe_message_keyを日本語表示に変換する', () => {
    expect(safeMessageLabel('citation_verified')).toBe('根拠情報を確認しました')
  })

  test('未知のsafe_message_keyは元の値を返す', () => {
    expect(safeMessageLabel('custom_key')).toBe('custom_key')
  })
})

describe('buildPayloadDiffRows', () => {
  test('編集payloadとの差分をkey順で返す', () => {
    expect(
      buildPayloadDiffRows(
        { title: '訪問準備', description: '資料を確認する' },
        { title: '訪問準備', description: '価格表を確認する' },
      ),
    ).toEqual([
      {
        key: 'description',
        before: '資料を確認する',
        after: '価格表を確認する',
        changed: true,
      },
      {
        key: 'title',
        before: '訪問準備',
        after: '訪問準備',
        changed: false,
      },
    ])
  })

  test('edited payloadがない場合は空配列を返す', () => {
    expect(buildPayloadDiffRows({ title: '訪問準備' }, null)).toEqual([])
  })
})

describe('hasPayloadChanges', () => {
  test('差分行に変更があればtrueを返す', () => {
    const rows = buildPayloadDiffRows(
      { title: '訪問準備' },
      { title: '訪問準備を更新' },
    )

    expect(hasPayloadChanges(rows)).toBe(true)
  })

  test('差分行がすべて変更なしならfalseを返す', () => {
    const rows = buildPayloadDiffRows(
      { title: '訪問準備', claim_ids: [] },
      { title: '訪問準備', claim_ids: [] },
    )

    expect(hasPayloadChanges(rows)).toBe(false)
  })
})

describe('getApprovalSubmitState', () => {
  test('編集がなければ元提案の承認だけを許可する', () => {
    expect(getApprovalSubmitState(true, false, [], [])).toEqual({
      canApproveOriginal: true,
      canApproveEdited: false,
      validationErrors: [],
    })
  })

  test('編集があれば編集承認だけを許可する', () => {
    expect(getApprovalSubmitState(true, true, [], [])).toEqual({
      canApproveOriginal: false,
      canApproveEdited: true,
      validationErrors: [],
    })
  })

  test('編集payloadが不正なら編集承認を許可しない', () => {
    expect(getApprovalSubmitState(true, true, [], ['body は必須です'])).toEqual({
      canApproveOriginal: false,
      canApproveEdited: false,
      validationErrors: ['body は必須です'],
    })
  })

  test('サーバ側検証エラーがあれば元提案の承認を許可しない', () => {
    expect(getApprovalSubmitState(true, false, [], [], ['invalid_payload'])).toEqual({
      canApproveOriginal: false,
      canApproveEdited: false,
      validationErrors: ['invalid_payload'],
    })
  })

  test('編集payloadのエラーとサーバ側検証エラーをまとめて返す', () => {
    expect(
      getApprovalSubmitState(true, true, [], ['body は必須です'], ['invalid_payload']),
    ).toEqual({
      canApproveOriginal: false,
      canApproveEdited: false,
      validationErrors: ['body は必須です', 'invalid_payload'],
    })
  })
})

describe('stringifyJsonValue', () => {
  test('表示用にJSON値を文字列化する', () => {
    expect(stringifyJsonValue({ due: '明日' })).toBe('{"due":"明日"}')
    expect(stringifyJsonValue(false)).toBe('false')
    expect(stringifyJsonValue(null)).toBe('')
  })
})

describe('buildApprovalPayload', () => {
  test('メール草案を編集したらsubjectとbodyでpayloadを作る', () => {
    expect(buildApprovalPayload('email_draft', '件名', '本文')).toEqual({
      subject: '件名',
      body: '本文',
    })
  })

  test('メモを編集したらtitleとbodyでpayloadを作る', () => {
    expect(buildApprovalPayload('memo', '議事メモ', '確認内容')).toEqual({
      title: '議事メモ',
      body: '確認内容',
    })
  })

  test('claim_idsがある提案を編集したらpayloadへ引き継ぐ', () => {
    expect(buildApprovalPayload('task', '宿題', '見積を送る', ['claim_001'])).toEqual({
      title: '宿題',
      description: '見積を送る',
      claim_ids: ['claim_001'],
    })
  })

  test('元payloadにclaim_idsがある場合は空配列も保持する', () => {
    expect(buildApprovalPayload('task', '宿題', '見積を送る', [], true)).toEqual({
      title: '宿題',
      description: '見積を送る',
      claim_ids: [],
    })
  })
})

describe('validateApprovalPayload', () => {
  test('メール草案の件名と本文が空ならsubjectとbodyのエラーを返す', () => {
    expect(validateApprovalPayload('email_draft', ' ', '')).toEqual([
      'subject は必須です',
      'body は必須です',
    ])
  })

  test('活動記録の内容が空ならdescriptionのエラーだけを返す', () => {
    expect(validateApprovalPayload('activity_log', '', ' ')).toEqual([
      'description は必須です',
    ])
  })
})

describe('getBusinessRecordHref', () => {
  test('活動記録なら編集画面へのリンクを返す', () => {
    expect(getBusinessRecordHref('visit', 7)).toBe('/visits/7/edit')
  })

  test('Agent専用レコードなら画面内アンカーへのリンクを返す', () => {
    expect(getBusinessRecordHref('agent_task', 12)).toBe(
      '#agent-business-record-agent-task-12',
    )
  })
})

describe('isApprovalExpired', () => {
  test('期限が現在時刻より前なら期限切れとして扱う', () => {
    expect(isApprovalExpired('2026-06-16T09:00:00', Date.parse('2026-06-16T10:00:00'))).toBe(
      true,
    )
  })

  test('期限がnullなら期限切れとして扱わない', () => {
    expect(isApprovalExpired(null, Date.parse('2026-06-16T10:00:00'))).toBe(false)
  })
})
