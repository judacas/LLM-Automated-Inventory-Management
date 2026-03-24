const nodeCrypto = require('crypto');

if (!globalThis.crypto) {
  globalThis.crypto = nodeCrypto.webcrypto;
}


require('dotenv').config();


const { AIProjectClient } = require('@azure/ai-projects');
const { DefaultAzureCredential } = require('@azure/identity');

const PROJECT_ENDPOINT = process.env.PROJECT_ENDPOINT;
const AGENT_NAME = process.env.AGENT_NAME;

// MCP tool calls can require explicit approval. When approvals are required and not
// provided, the Responses API returns a 400 listing pending approval request IDs
// (e.g., "mcpr_...").
//
// For a demo/admin portal experience we default to auto-approving those requests.
// You can disable this by setting MCP_AUTO_APPROVE=false.
const MCP_AUTO_APPROVE = String(process.env.MCP_AUTO_APPROVE ?? 'true').toLowerCase() !== 'false';

if (!PROJECT_ENDPOINT) {
  throw new Error('Missing PROJECT_ENDPOINT in .env');
}

if (!AGENT_NAME) {
  throw new Error('Missing AGENT_NAME in .env');
}

const projectClient = new AIProjectClient(
  PROJECT_ENDPOINT,
  new DefaultAzureCredential()
);

let openAIClientPromise = null;

async function getOpenAIClient() {
  if (!openAIClientPromise) {
    openAIClientPromise = projectClient.getOpenAIClient();
  }
  return openAIClientPromise;
}

async function createConversation() {
  const openai = await getOpenAIClient();
  return await openai.conversations.create();
}

async function sendMessageToAgent({ conversationId, message }) {
  const openai = await getOpenAIClient();

  const agentReference = {
    type: 'agent_reference',
    name: AGENT_NAME
  };

  async function createAgentResponse(input) {
    return await openai.responses.create({
      conversation: conversationId,
      input,
      agent_reference: agentReference
    });
  }

  async function approveMcpRequests(approvalRequestIds) {
    const inputItems = approvalRequestIds.map((approvalRequestId) => ({
      type: 'mcp_approval_response',
      approval_request_id: approvalRequestId,
      approve: true,
    }));

    return await createAgentResponse(inputItems);
  }

  try {
    return await createAgentResponse(message);
  } catch (err) {
    const msg = String(err?.message || err);

    // Example:
    // "400 The following MCP approval requests do not have an approval: mcpr_..."
    if (!msg.toLowerCase().includes('mcp approval')) {
      throw err;
    }

    const approvalIds = Array.from(msg.matchAll(/\bmcpr_[a-z0-9]+\b/gi)).map((m) => m[0]);
    const uniqueApprovalIds = [...new Set(approvalIds)];

    if (!uniqueApprovalIds.length) {
      throw err;
    }

    if (!MCP_AUTO_APPROVE) {
      const approvalList = uniqueApprovalIds.join(', ');
      throw new Error(
        `MCP tool call requires approval (set MCP_AUTO_APPROVE=true to auto-approve). Pending approval request(s): ${approvalList}`
      );
    }

    // Approve pending tool call(s) for this conversation, then retry the user's message.
    await approveMcpRequests(uniqueApprovalIds);
    return await createAgentResponse(message);
  }
}

module.exports = {
  createConversation,
  sendMessageToAgent
};