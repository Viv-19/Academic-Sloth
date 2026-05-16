const { PrismaClient } = require('@prisma/client');
const bcrypt = require('bcryptjs');
const prisma = new PrismaClient();

async function main() {
    const email = 'e2e@test.com';
    const password = 'password123';
    
    // Delete if exists
    await prisma.user.deleteMany({where: {email}});
    
    const salt = await bcrypt.genSalt(10);
    const hashedPassword = await bcrypt.hash(password, salt);
    
    await prisma.user.create({
        data: {
            name: 'E2E Test',
            email: email,
            password_hash: hashedPassword,
            otp: '123456',
            otp_expiry: new Date(Date.now() + 10 * 60 * 1000),
            is_verified: true
        }
    });
    console.log(`Test user created. Email: ${email}, Password: ${password}`);
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
