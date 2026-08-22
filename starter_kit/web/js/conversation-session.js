// Browser-side pointer to server-owned conversation and active circuit state.

const STORAGE_KEY = 'loomq.conversationSession';

export class ConversationSession {
  constructor(storage = window.sessionStorage) {
    this.storage = storage;
    this.state = this.load();
  }

  requestContext() {
    const payload = {};
    if (this.state.conversationId) payload.conversation_id = this.state.conversationId;
    if (this.state.artifact?.id) {
      payload.active_artifact_id = this.state.artifact.id;
      payload.expected_version = this.state.artifact.version;
    }
    return payload;
  }

  update(response) {
    this.state = {
      conversationId: response.conversation_id || this.state.conversationId || null,
      artifact: response.active_artifact || null,
    };
    this.persist();
    return this.state;
  }

  clear() {
    this.state = { conversationId: null, artifact: null };
    this.storage.removeItem(STORAGE_KEY);
  }

  load() {
    try {
      const stored = JSON.parse(this.storage.getItem(STORAGE_KEY));
      if (stored && typeof stored === 'object') {
        return {
          conversationId: typeof stored.conversationId === 'string' ? stored.conversationId : null,
          artifact: stored.artifact?.id ? stored.artifact : null,
        };
      }
    } catch (_error) {
      this.storage.removeItem(STORAGE_KEY);
    }
    return { conversationId: null, artifact: null };
  }

  persist() {
    this.storage.setItem(STORAGE_KEY, JSON.stringify(this.state));
  }
}
