import { useState } from 'react';

function ChatWindow() {
    const [messages, setMessages] = useState([]);
    const [inputValue, setInputValue] = useState('');
    const [status, setStatus] = useState('idle');

    const handleInputChange = (e) => {
        setInputValue(e.target.value);
    };

    const handleSendMessage = async (e) => {
        e.preventDefault();
        if (!inputValue.trim()) return;

        const userMessage = { role: 'user', text: inputValue };
        setMessages((prev) => [...prev, userMessage]);
        setInputValue('');
        setStatus('loading');

        // TODO: Replace with actual API call to send the message and receive a response

        try {
            // const response = await fetch('/api/query', {
            //     method: 'POST',
            //     headers: { 'Content-Type': 'application/json' },
            //     body: JSON.stringify({ question: userMessage.text }),
            // });
            // if (!response.ok) {
            // const errorData = await response.json();
            // throw new Error(errorData.detail || 'Query failed');
            // }
            // const data = await response.json();
            // const mockAnswer = { role: 'assistant', text: data.answer };

            await new Promise((resolve) => setTimeout(resolve, 800));
            const mockAnswer = { role: 'assistant', text: `Mock answer to: ${userMessage.text}` };

            setMessages((prev) => [...prev, mockAnswer]);
            setStatus('idle');
            } catch (error) {
                console.error(error);
                setStatus('error');
            }
    };

    return (
        <div className="chat-window">
            <div className="chat-messages" aria-live="polite">
                {messages.length === 0 && (
                    <p className="chat-window__empty">Ask a question about your uploaded notes to get started.</p>
                )}

                {messages.map((msg, index) => (
                    <div key={index} className={`chat-window__message chat-window__message--${msg.role}`}>
                        <p>{msg.text}</p>
                    </div>
                ))}

                {status === 'loading' && <p className="chat-window__loading">Thinking...</p>}
                {status === 'error' && <p className="chat-window__error">Something went wrong. Try again.</p>}
            </div>

            <form className="chat-window__input" onSubmit={handleSendMessage}>
                <input
                    type="text"
                    value={inputValue}
                    onChange={handleInputChange}
                    placeholder="Ask a question..."
                    disabled={status === 'loading'}
                />
                <button type='submit' disabled={!inputValue.trim() || status === 'loading'}>Send</button>
            </form>
        </div>
    );
}

export default ChatWindow;