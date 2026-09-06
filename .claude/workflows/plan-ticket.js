export const meta = {
  name: 'plan-ticket',
  description: 'Plan an engineering ticket with the planner agent, then stop for human approval',
  whenToUse: 'Pass a ticket description as args.ticket. Returns the plan and stops — approve it, then run implement-ticket.js with the plan.',
  phases: [
    { title: 'Plan', detail: 'planner agent breaks the ticket into small, shippable PRs' },
  ],
}

phase('Plan')

if (!args || !args.ticket) {
  throw new Error('plan-ticket requires args.ticket (the ticket text)')
}

const plan = await agent(
  `Plan this engineering ticket as a sequence of small, safe, independently shippable pull requests.\n\nTicket:\n${args.ticket}`,
  { agentType: 'planner', phase: 'Plan', label: 'planner' }
)

log('Plan ready. Review it, then run implement-ticket.js with { ticket, plan } once approved.')

return { ticket: args.ticket, plan }
