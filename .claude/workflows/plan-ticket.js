export const meta = {
  name: 'plan-ticket',
  description: 'Plan a request with the planner agent, then stop for human approval',
  whenToUse: 'Pass a request as args.request — a ticket, or plain requirement text. Returns the plan and stops — approve it, then run implement-ticket.js with the plan.',
  phases: [
    { title: 'Plan', detail: 'planner agent breaks the request into small, shippable PRs' },
  ],
}

phase('Plan')

if (!args || !args.request) {
  throw new Error('plan-ticket requires args.request (a ticket, or plain requirement text)')
}

const plan = await agent(
  `Plan this request as a sequence of small, safe, independently shippable pull requests.\n\nRequest:\n${args.request}`,
  { agentType: 'planner', phase: 'Plan', label: 'planner' }
)

log('Plan ready. Review it, then run implement-ticket.js with { request, plan } once approved.')

return { request: args.request, plan }
