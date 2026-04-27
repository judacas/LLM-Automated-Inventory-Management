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
// provided, the Responses API may:
// - throw a 400 listing pending approval request IDs (e.g., "mcpr_...")
// - OR return a normal response that includes an output item of type
//   "mcp_approval_request".
//
// This project intentionally does NOT auto-approve MCP tool calls. Approvals should
// be handled in the Foundry portal for visibility and control.

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

  function extractMcpApprovalRequestIdsFromResponse(response) {
    const out = response?.output;
    if (!Array.isArray(out)) return [];

    const ids = [];
    for (const item of out) {
      if (item?.type !== 'mcp_approval_request') continue;
      const candidateIds = [item?.approval_request_id, item?.approvalRequestId, item?.id]
        .filter((v) => typeof v === 'string');
      for (const id of candidateIds) ids.push(id);
    }

    return [...new Set(ids)];
  }

  function extractMcpApprovalRequestIdsFromErrorMessage(message) {
    // Example:
    // "400 The following MCP approval requests do not have an approval: mcpr_..."
    const ids = Array.from(String(message).matchAll(/\bmcpr_[a-z0-9]+\b/gi)).map((m) => m[0]);
    return [...new Set(ids)];
  }

  try {
    const response = await createAgentResponse(message);

    const approvalIds = extractMcpApprovalRequestIdsFromResponse(response);
    if (approvalIds.length) {
      const approvalList = approvalIds.join(', ');
      throw new Error(
        `MCP tool call requires approval in Foundry portal. Pending approval request(s): ${approvalList}`
      );
    }

    return response;
  } catch (err) {
    const msg = String(err?.message || err);

    if (!msg.toLowerCase().includes('mcp approval')) {
      throw err;
    }

    const approvalIds = extractMcpApprovalRequestIdsFromErrorMessage(msg);
    if (!approvalIds.length) {
      throw err;
    }

    const approvalList = approvalIds.join(', ');
    throw new Error(
      `MCP tool call requires approval in Foundry portal. Pending approval request(s): ${approvalList}`
    );
  }
}

module.exports = {
  createConversation,
  sendMessageToAgent
};