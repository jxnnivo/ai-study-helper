// api.js
// Thin wrapper around the backend's three endpoints (upload, query, quiz).
// Drop this into frontend/src/ and import from your React components.
//
// If your backend runs on a different host/port than localhost:8000,
// update API_BASE_URL below.

const API_BASE_URL = "http://localhost:8000";

async function handleResponse(response) {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // response body wasn't JSON -- fall back to the plain status text
    }
    throw new Error(`Request failed (${response.status}): ${detail}`);
  }
  return response.json();
}

/**
 * Upload a PDF for ingestion.
 * @param {File} file - a File object, e.g. from an <input type="file"> element
 * @returns {Promise<{filename: string, pages_processed: number, chunks_stored: number}>}
 */
export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/upload`, {
    method: "POST",
    body: formData,
    // Deliberately no Content-Type header here -- the browser sets the
    // multipart/form-data boundary automatically for FormData bodies.
    // Setting it manually breaks the upload.
  });
  return handleResponse(response);
}

/**
 * Ask a question against the uploaded notes.
 * @param {string} question
 * @param {number} [topK=5] - how many source chunks to retrieve
 * @returns {Promise<{
 *   question: string,
 *   answer: string,
 *   sources: Array<{source: string, page_number: number, text: string}>
 * }>}
 */
export async function askQuestion(question, topK = 5) {
  const response = await fetch(`${API_BASE_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: topK }),
  });
  return handleResponse(response);
}

/**
 * Generate a multiple-choice quiz on a topic from the uploaded notes.
 * @param {string} topic
 * @param {number} [numQuestions=5]
 * @param {number} [topK=5] - how many source chunks to retrieve
 * @returns {Promise<{
 *   topic: string,
 *   questions: Array<{question: string, options: string[], correct_answer: string}>
 * }>}
 */
export async function generateQuiz(topic, numQuestions = 5, topK = 5) {
  const response = await fetch(`${API_BASE_URL}/quiz`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, num_questions: numQuestions, top_k: topK }),
  });
  return handleResponse(response);
}