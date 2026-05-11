import { auth } from './auth.js';

const API_URL = 'http://localhost:3000/api/documents';

export const upload = {
    /**
     * Uploads a PDF to the backend Document Ingestion API
     * @param {File} file - The file selected by the user
     */
    async uploadPaper(file) {
        try {
            // Check if user is logged in
            if (!auth.isAuthenticated()) {
                alert('You must be logged in to upload a document.');
                window.location.href = 'signin.html';
                return;
            }

            // Create a FormData object (required for multipart/form-data)
            const formData = new FormData();
            formData.append('pdfFile', file); // 'pdfFile' must match what our multer middleware expects!

            // Add loading state to UI (Optional, but good for UX)
            const uploadBtnLabel = document.getElementById('file-name');
            const originalText = uploadBtnLabel ? uploadBtnLabel.textContent : '';
            if (uploadBtnLabel) uploadBtnLabel.textContent = 'Uploading... Please wait.';

            const response = await fetch(`${API_URL}/upload`, {
                method: 'POST',
                headers: {
                    // We DO NOT set 'Content-Type' here! 
                    // fetch automatically sets it to multipart/form-data with the correct boundary when passing FormData.
                    'Authorization': `Bearer ${auth.getToken()}`
                },
                body: formData
            });

            const data = await response.json();

            // Restore UI
            if (uploadBtnLabel) uploadBtnLabel.textContent = originalText;

            if (!response.ok) {
                alert(data.message || 'Failed to upload document.');
                return;
            }

            // Success!
            alert('Document uploaded successfully! It is now pending AI processing.');
            
            // Reload the page to show the newly added document in the recent papers list
            window.location.reload();

        } catch (error) {
            console.error('Error during document upload:', error);
            alert('A network error occurred while uploading. Is the server running?');
        }
    }
};
