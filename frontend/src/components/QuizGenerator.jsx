import { useState } from 'react';

const mockQuestions = [
  {
    question: 'What does RAG stand for in this project?',
    options: ['Retrieval-Augmented Generation', 'Rapid Application Growth', 'Random Access Grid', 'Recursive Answer Generator'],
    correctAnswer: 'Retrieval-Augmented Generation',
  },
  {
    question: 'Which library handles PDF parsing in the backend?',
    options: ['PyPDF2', 'pdfplumber', 'PDFMiner', 'fitz'],
    correctAnswer: 'pdfplumber',
  },
  {
    question: 'Where are document embeddings stored?',
    options: ['PostgreSQL', 'Chroma', 'Redis', 'MongoDB'],
    correctAnswer: 'Chroma',
  },
];

function QuizGenerator() {
    const [currentIndex, setCurrentIndex] = useState(0);
    const [selectedAnswer, setSelectedAnswer] = useState(null);
    const [hasSubmitted, setHasSubmitted] = useState(false);
    const [score, setScore] = useState(0);
    const [quizComplete, setQuizComplete] = useState(false);

    const currentQuestion = mockQuestions[currentIndex];

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
        if (currentIndex + 1 < mockQuestions.length) {
        setCurrentIndex((prev) => prev + 1);
        setSelectedAnswer(null);
        setHasSubmitted(false);
        } else {
        setQuizComplete(true);
        }
    };

    const handleRestart = () => {
        setCurrentIndex(0);
        setSelectedAnswer(null);
        setHasSubmitted(false);
        setScore(0);
        setQuizComplete(false);
    };

    if (quizComplete) {
        return (
        <div className="quiz">
            <h2>Quiz complete!</h2>
            <p>You scored {score} out of {mockQuestions.length}</p>
            <button onClick={handleRestart}>Try again</button>
        </div>
        );
    }

    return (
        <div className="quiz">
            <p className="quiz__progress">Question {currentIndex + 1} of {mockQuestions.length}</p>
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
            {currentIndex + 1 < mockQuestions.length ? 'Next question' : 'See results'}
            </button>
        )}
        </div>
    );
}

export default QuizGenerator;