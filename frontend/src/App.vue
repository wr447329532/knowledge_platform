<template>
  <router-view />
</template>

<script setup>
</script>

<style>
/* 商务蓝主题 - 央国企风格 */
:root {
  --primary: #1a56b0;
  --primary-dark: #0d3d7a;
  --primary-light: #2d6bc9;
  --primary-bg: #e8f0fa;
  --danger: #c62828;
  --danger-hover: #b71c1c;
  --success: #2e7d32;
  --success-bg: #e8f5e9;
  --text: #1a1a1a;
  --text-secondary: #5c5c5c;
  --border: #e5e7eb;
  --bg-page: #f5f6f8;
  --card-shadow: 0 1px 4px rgba(0,0,0,0.06);
  --sidebar-bg: #1a1f3a;
  --sidebar-text: rgba(255,255,255,0.95);
  --sidebar-text-muted: rgba(255,255,255,0.6);
  --sidebar-accent: #4a90e2;
  --radius: 6px;
  --header-height: 56px;
  --sidebar-width: 256px;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "PingFang SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 14px;
  color: var(--text);
  background: #fff;
  line-height: 1.5;
}
#app { min-height: 100vh; }
a { color: var(--primary); text-decoration: none; }
a:hover { text-decoration: underline; color: var(--primary-dark); }
button {
  cursor: pointer;
  padding: 8px 16px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: #fff;
  font-size: 14px;
  transition: background 0.2s, border-color 0.2s;
}
button:hover { background: #f5f5f5; border-color: #999; }
button.primary {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}
button.primary:hover { background: var(--primary-dark); border-color: var(--primary-dark); }
button.danger { background: var(--danger); color: #fff; border-color: var(--danger); }
button.danger:hover { background: var(--danger-hover); border-color: var(--danger-hover); }
input, select {
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 14px;
  transition: border-color 0.2s;
}
input:focus, select:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--primary-bg);
}
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); }
th { background: #f7f8fa; font-weight: 600; color: var(--text); }
tr:hover { background: #fafbfc; }
.card {
  background: #fff;
  border-radius: var(--radius);
  box-shadow: var(--card-shadow);
  padding: 20px;
  margin-bottom: 16px;
  border: 1px solid rgba(0,0,0,0.06);
}
</style>
