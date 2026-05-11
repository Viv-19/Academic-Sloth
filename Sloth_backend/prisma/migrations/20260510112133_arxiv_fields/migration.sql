-- AlterTable
ALTER TABLE "Document" ADD COLUMN     "arxiv_id" TEXT,
ADD COLUMN     "source" TEXT NOT NULL DEFAULT 'local';
