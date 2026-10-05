const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "";


/**
 * Send a natural-language question to the CommercePilot API.
 */
export async function askCommercePilot(question) {
  const response = await fetch(
    `${API_BASE_URL}/api/ask`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question,
      }),
    },
  );

  if (!response.ok) {
    let message =
      "CommercePilot could not process the request.";

    try {
      const errorData = await response.json();

      if (
        typeof errorData.detail === "string"
      ) {
        message = errorData.detail;
      }
    } catch {
      // Keep the generic message if the server
      // does not return JSON.
    }

    throw new Error(message);
  }

  return response.json();
}