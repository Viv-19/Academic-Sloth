const multer = require('multer');
const path = require('path');
const fs = require('fs');

// Ensure the uploads directory exists
const uploadDir = path.join(__dirname, '../../../Sloth_backend/uploads');
if (!fs.existsSync(uploadDir)) {
    fs.mkdirSync(uploadDir, { recursive: true });
}

// Configure where and how Multer saves the incoming files
const storage = multer.diskStorage({
    destination: function (req, file, cb) {
        // 'cb' is the callback function we call when we are done.
        // null means no error, uploadDir is the folder path.
        cb(null, uploadDir);
    },
    filename: function (req, file, cb) {
        // We generate a unique filename so multiple users uploading "paper.pdf" don't overwrite each other!
        // We append the current timestamp to the original filename.
        const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
        cb(null, uniqueSuffix + '-' + file.originalname);
    }
});

// Configure the Multer instance with our storage rules and a strict file filter
const upload = multer({
    storage: storage,
    limits: {
        fileSize: 20 * 1024 * 1024, // Set a hard limit of 20MB per file to prevent server crashes
    },
    fileFilter: function (req, file, cb) {
        // We only want to accept PDF documents.
        if (file.mimetype === 'application/pdf') {
            cb(null, true); // Accept the file
        } else {
            cb(new Error('Only PDF files are allowed!'), false); // Reject the file
        }
    }
});

module.exports = upload;
