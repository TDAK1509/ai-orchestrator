export const meta = {
  name: 'implement-ticket',
  description: 'Implement a plan, looping developer <-> code-review until approved',
  whenToUse: 'Pass args.plan — plan text, or a link to it. Loops developer and code-review agents until the reviewer approves or the round cap is hit.',
  phases: [
    { title: 'Develop', detail: 'developer agent implements the plan or addresses review feedback' },
    { title: 'Review', detail: 'code-review agent checks the implementation against the plan' },
  ],
}

const MAX_ROUNDS = 3

const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    approved: { type: 'boolean' },
    feedback: { type: 'string' },
  },
  required: ['approved', 'feedback'],
}

if (!args || !args.plan) {
  throw new Error('implement-ticket requires args.plan (plan text, or a link to it)')
}

let approved = false
let feedback = null
let devResult = null
let round = 0

while (!approved && round < MAX_ROUNDS) {
  round++

  phase('Develop')
  const devPrompt = feedback
    ? `Plan:\n${args.plan}\n\nA code reviewer requested these changes to your previous implementation — address them:\n${feedback}`
    : `Implement this plan:\n${args.plan}`
  devResult = await agent(devPrompt, { agentType: 'developer', phase: 'Develop', label: `develop-round-${round}` })

  phase('Review')
  const review = await agent(
    `Review the current branch against main for correctness, scope, security, and performance.\n\nPlan:\n${args.plan}\n\nDeveloper's summary of this round's changes:\n${devResult}`,
    { agentType: 'code-review', phase: 'Review', label: `review-round-${round}`, schema: REVIEW_SCHEMA }
  )

  approved = review.approved
  feedback = review.feedback
  log(`Round ${round}: ${approved ? 'approved' : 'changes requested'}`)
}

if (!approved) {
  log(`Stopped after ${MAX_ROUNDS} rounds without approval — needs human review.`)
}

return { approved, rounds: round, finalFeedback: feedback, devResult }
