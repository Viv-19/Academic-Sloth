const app = require('./app');

// You can eventually replace this by reading from process.env.PORT
// We'll set up the .env file loading in the next step.
const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
    console.log(`=================================`);
    console.log(`🚀 Server running on port ${PORT}`);
    console.log(`=================================`);
    console.log(`You can test the health check at:`);
    console.log(`http://localhost:${PORT}/health`);
});
