const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
    const user = await prisma.user.findUnique({where: {email: 'test@test.com'}});
    console.log('User OTP:', user?.otp);
    
    await prisma.user.update({
        where: {email: 'test@test.com'}, 
        data: {is_verified: true}
    });
    console.log('User test@test.com is now verified.');
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
