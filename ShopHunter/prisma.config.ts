import { defineConfig } from "prisma/config";

// 优先使用环境变量中的 DATABASE_URL（云端 Turso）；
// 如果没有设置，则在本地回退到内置的 SQLite 文件。
const dbUrl = process.env.DATABASE_URL ?? "file:./prisma/sqlite";

export default defineConfig({
  datasource: {
    url: dbUrl
  }
});

