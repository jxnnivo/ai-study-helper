import { useState } from 'react';
import { generateQuiz } from '../api/client';

function QuizGenerator() {
    const [topic, setTopic] = useState('');
    const [questions, setQuestions] = useState([]);
    const [quizStatus, setQuizStatus] = useState('idle'); // 'idle' | 'loading' | 'ready' | 'error'
    const [errorMessage, setErrorMessage] = useState('');

    const [currentIndex, setCurrentIndex] = useState(0);
    const [selectedAnswer, setSelectedAnswer] = useState(null);
    const [hasSubmitted, setHasSubmitted] = useState(false);
    const [score, setScore] = useState(0);
    const [quizComplete, setQuizComplete] = useState(false);

    const currentQuestion = questions[currentIndex];

    const handleGenerateQuiz = async (e) => {
        e.preventDefault();
        if (!topic.trim()) return;

        setQuizStatus('loading');
        setErrorMessage('');

        try {
            const data = await generateQuiz(topic);
            const mappedQuestions = data.questions.map((q) => ({
                question: q.question,
                options: q.options,
                correctAnswer: q.correct_answer,
            }));
            setQuestions(mappedQuestions);
            setCurrentIndex(0);
            setSelectedAnswer(null);
            setHasSubmitted(false);
            setScore(0);
            setQuizComplete(false);
            setQuizStatus('ready');
        } catch (error) {
            console.error(error);
            setErrorMessage(error.message);
            setQuizStatus('error');
        }
    };

    const handleSelectAnswer = (option) => {
        if (hasSubmitted) return;
        setSelectedAnswer(option);
    };

    const handleSubmitAnswer = () => {
        if (!selectedAnswer) return;
        setHasSubmitted(true);
        if (selectedAnswer === currentQuestion.correctAnswer) {
            setScore((prev) => prev + 1);
        }
    };

    const handleNext = () => {
        if (currentIndex + 1 < questions.length) {
            setCurrentIndex((prev) => prev + 1);
            setSelectedAnswer(null);
            setHasSubmitted(false);
        } else {
            setQuizComplete(true);
        }
    };

    const handleRestart = () => {
        setQuestions([]);
        setTopic('');
        setCurrentIndex(0);
        setSelectedAnswer(null);
        setHasSubmitted(false);
        setScore(0);
        setQuizComplete(false);
        setQuizStatus('idle');
    };

    if (quizStatus === 'idle' || quizStatus === 'loading' || quizStatus === 'error') {
        return (
            <div className="quiz">
                <form className="quiz__setup" onSubmit={handleGenerateQuiz}>
                    <label htmlFor="quiz-topic">What topic do you want to be quizzed on?</label>
                    <input
                        id="quiz-topic"
                        type="text"
                        value={topic}
                        onChange={(e) => setTopic(e.target.value)}
                        placeholder="e.g. photosynthesis"
                        disabled={quizStatus === 'loading'}
                    />
                    <button type="submit" disabled={!topic.trim() || quizStatus === 'loading'}>
                        {quizStatus === 'loading' ? 'Generating...' : 'Generate Quiz'}
                    </button>
                </form>
                {quizStatus === 'error' && (
                    <p className="quiz__error">{errorMessage || 'Could not generate a quiz. Try again.'}</p>
                )}
            </div>
        );
    }

    if (quizComplete) {
        return (
            <div className="quiz">
                <h2>Quiz complete!</h2>
                <p>You scored {score} out of {questions.length}</p>
                <button onClick={handleRestart}>Try again</button>
            </div>
        );
    }

    return (
        <div className="quiz">
            <p className="quiz__progress">Question {currentIndex + 1} of {questions.length}</p>
            <h2 className="quiz__question">{currentQuestion.question}</h2>

            <div className="quiz__options">
                {currentQuestion.options.map((option) => {
                    const isSelected = selectedAnswer === option;
                    const isCorrect = option === currentQuestion.correctAnswer;

                    let optionClass = 'quiz__option';

                    if (hasSubmitted && isSelected) {
                        optionClass += isCorrect ? ' quiz__option--correct' : ' quiz__option--incorrect';
                    } else if (hasSubmitted && isCorrect) {
                        optionClass += ' quiz__option--correct';
                    } else if (isSelected) {
                        optionClass += ' quiz__option--selected';
                    }

                    return (
                        <button
                            key={option}
                            className={optionClass}
                            onClick={() => handleSelectAnswer(option)}
                            disabled={hasSubmitted}
                        >
                            {option}
                        </button>
                    );
                })}
            </div>

            {!hasSubmitted ? (
                <button onClick={handleSubmitAnswer} disabled={!selectedAnswer}>
                    Submit
                </button>
            ) : (
                <button onClick={handleNext}>
                    {currentIndex + 1 < questions.length ? 'Next question' : 'See results'}
                </button>
            )}
        </div>
    );
}

export default QuizGenerator;