const { PrismaClient } = require('@prisma/client');

// Initialize Prisma Client
// We do this in a separate file so we only create ONE instance of Prisma
// and reuse it throughout the entire application.
const prisma = new PrismaClient();

module.exports = prisma;
