import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ReportNextBestAction from '~/components/report/ReportNextBestAction.vue'

const setPlanActionDone = vi.fn()

vi.mock('~/composables/api/useReportApi', () => ({
  useReportApi: () => ({
    setPlanActionDone,
    createPlanAction: vi.fn(),
    updatePlanAction: vi.fn(),
    deletePlanAction: vi.fn()
  })
}))

const UCheckbox = {
  props: ['modelValue', 'disabled'],
  emits: ['update:modelValue'],
  template: '<button class="test-checkbox" type="button" :disabled="disabled" @click="$emit(\'update:modelValue\', !modelValue)">{{ modelValue }}</button>'
}

const plan = {
  job_id: 'job-1',
  next_month_plan: {
    plan_month: 1,
    phase_label: '前期',
    items: [{
      focus_dimension: 'learning',
      focus_label: '学习',
      milestone: '形成学习成果',
      custom_actions: [
        { action_uid: 'action-1', text: '任务一', done: false },
        { action_uid: 'action-2', text: '任务二', done: false }
      ]
    }]
  }
}

describe('report action checklist', () => {
  beforeEach(() => setPlanActionDone.mockReset())

  it('allows a second task to be checked while the first save is pending and serializes writes', async () => {
    let resolveFirst!: (value: unknown) => void
    setPlanActionDone
      .mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve }))
      .mockResolvedValueOnce({ done: true })

    const wrapper = mount(ReportNextBestAction, {
      props: { reportId: 32, plan },
      global: {
        stubs: {
          UCheckbox,
          UButton: { template: '<button type="button"><slot/></button>' },
          UIcon: { template: '<i />' },
          UModal: { template: '<div><slot name="body"/><slot name="footer"/></div>' },
          UFormField: { template: '<label><slot/></label>' },
          UInput: { template: '<input />' },
          UTextarea: { template: '<textarea />' }
        }
      }
    })

    let boxes = wrapper.findAll('.test-checkbox')
    await boxes[0]!.trigger('click')
    boxes = wrapper.findAll('.test-checkbox')
    expect(boxes[0]!.attributes('disabled')).toBeDefined()
    expect(boxes[1]!.attributes('disabled')).toBeUndefined()

    await boxes[1]!.trigger('click')
    expect(setPlanActionDone).toHaveBeenCalledTimes(1)

    resolveFirst!({ done: true })
    await flushPromises()
    expect(setPlanActionDone).toHaveBeenCalledTimes(2)
    expect(setPlanActionDone.mock.calls.map(call => call[1].action_uid)).toEqual(['action-1', 'action-2'])
  })
})
