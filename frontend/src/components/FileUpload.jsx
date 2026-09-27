import { useState, useRef } from 'react';

function FileUpload() {
    const [selectedFile, setSelectedFile] = useState(null);
    const [isDragging, setIsDragging] = useState(false);
    const [status, setStatus] = useState('idle');
    const inputRef = useRef(null);
    const [errorMessage, setErrorMessage] = useState('');

    const isValidFileType = (file) => {
        const allowedExtensions = ['.pdf', '.docx'];
        const fileName = file.name.toLowerCase();
        return allowedExtensions.some((ext) => fileName.endsWith(ext));
    };

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            if (!isValidFileType(file)) {
                setErrorMessage('Only PDF and DOCX files are supported.');
                setStatus('error');
                return;
            }
            setSelectedFile(file);
            setStatus('idle');
        }
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = () => {
        setIsDragging(false);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragging(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            const file = e.dataTransfer.files[0];
            if (!isValidFileType(file)) {
                setErrorMessage('Only PDF and DOCX files are supported.');
                setStatus('error');
                return;
            }
            setSelectedFile(file);
            setStatus('idle');
        }
    };

    const handleUpload = async () => {
        if (!selectedFile) return;
        setStatus('uploading');
        setErrorMessage('');

        try {
            const formData = new FormData();
            formData.append('file', selectedFile);

            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Upload failed');
            }

            const data = await response.json();
            console.log('Upload successful:', data);

            setStatus('success');

        } catch (error) {
            console.error(error);
            setErrorMessage(error.message);
            setStatus('error');
        }
    };

    return (
        <div className="file-upload">
            <div
                className={`file-upload__dropzone ${isDragging ? 'file-upload__dropzone--active' : ''}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => inputRef.current.click()}
                onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        inputRef.current.click();
                    }
                }}
                role="button"
                tabIndex={0}
                aria-label="Upload a PDF or DOCX file"
                >
                <input
                    ref={inputRef}
                    type="file"
                    accept=".pdf,.docx"
                    onChange={handleFileChange}
                    style={{ display: 'none' }}
                />
                {selectedFile ? (
                    <p>{selectedFile.name}</p>
                ) : (
                    <p>Drag & drop a file here or click to select</p>
                )}
            </div>

            <button
                onClick={handleUpload}
                disabled={!selectedFile || status === 'uploading'}
            >
                {status === 'uploading' ? 'Uploading...' : 'Upload'}
            </button>

            {status === 'success' && <p className="file-upload__status">Upload successful</p>}
            {status === 'error' && <p className="file-upload__status file-upload__status--error">{errorMessage || 'Upload failed. Try again.'}</p>}
        </div>
    );
}

export default FileUpload;