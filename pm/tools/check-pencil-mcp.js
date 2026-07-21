#!/usr/bin/env node

/**
 * Pencil 环境检测脚本（增强版）
 *
 * 检测两项内容：
 * 1. VSCode 是否安装 Pencil 扩展
 * 2. Pencil MCP 服务器配置是否存在
 *
 * 注意：此脚本只能检测配置文件，无法验证 MCP 服务器实际连接状态。
 * 最终确认方式是直接调用 mcp__pencil__get_style_guide_tags 工具。
 *
 * 使用方法:
 *   node scripts/check-pencil-mcp.js
 *
 * 返回值:
 *   0 - Pencil 扩展已安装 且 MCP 配置存在
 *   1 - Pencil 扩展未安装
 *   2 - 检测失败
 *   3 - 扩展已安装 但 MCP 配置可能缺失（不代表 MCP 未连接）
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

/**
 * 查找 VSCode 扩展目录
 */
function findVSCodeExtensionsPath() {
  const platform = os.platform();
  const homeDir = os.homedir();

  const possiblePaths = {
    win32: [
      path.join(homeDir, '.vscode', 'extensions'),
      path.join(process.env.APPDATA || '', 'Code', 'User', 'extensions'),
      path.join(process.env.USERPROFILE || '', '.vscode', 'extensions')
    ],
    darwin: [
      path.join(homeDir, '.vscode', 'extensions'),
      path.join(homeDir, 'Library', 'Application Support', 'Code', 'User', 'extensions')
    ],
    linux: [
      path.join(homeDir, '.vscode', 'extensions'),
      path.join(homeDir, '.config', 'Code', 'User', 'extensions')
    ]
  };

  const paths = possiblePaths[platform] || [];

  for (const extPath of paths) {
    if (fs.existsSync(extPath)) {
      return extPath;
    }
  }

  return null;
}

/**
 * 检查 Claude Code MCP 配置中是否有 Pencil
 */
function checkPencilMcpConfig() {
  const homeDir = os.homedir();
  const platform = os.platform();

  // Claude Code 配置文件位置
  const configPaths = {
    win32: [
      path.join(homeDir, '.claude', 'config.json'),
      path.join(homeDir, 'AppData', 'Roaming', 'Claude', 'config.json'),
      path.join(process.env.APPDATA || '', 'Claude', 'config.json')
    ],
    darwin: [
      path.join(homeDir, '.claude', 'config.json'),
      path.join(homeDir, 'Library', 'Application Support', 'Claude', 'config.json')
    ],
    linux: [
      path.join(homeDir, '.claude', 'config.json'),
      path.join(homeDir, '.config', 'claude', 'config.json')
    ]
  };

  const paths = configPaths[platform] || [];

  for (const configPath of paths) {
    if (!fs.existsSync(configPath)) continue;

    try {
      const configContent = fs.readFileSync(configPath, 'utf-8');
      const config = JSON.parse(configContent);

      // 检查 MCP 服务器配置中是否有 pencil
      if (config.mcpServers && config.mcpServers.pencil) {
        return { found: true, configPath };
      }

      // 检查是否有其他可能的 pencil 相关配置
      const mcpServers = config.mcpServers || {};
      for (const key of Object.keys(mcpServers)) {
        if (key.toLowerCase().includes('pencil')) {
          return { found: true, configPath, key };
        }
      }
    } catch (error) {
      // 配置文件解析失败，继续检查下一个
      continue;
    }
  }

  return { found: false };
}

/**
 * 检查是否安装了 Pencil 扩展
 */
function checkPencilExtension() {
  const extensionsPath = findVSCodeExtensionsPath();

  if (!extensionsPath) {
    console.error('无法找到 VSCode 扩展目录');
    process.exit(2);
  }

  try {
    const extensions = fs.readdirSync(extensionsPath);

    // Pencil 扩展的 ID 可能是: pencil.pencil 或其他变体
    const pencilExtensions = extensions.filter(ext =>
      ext.toLowerCase().includes('pencil')
    );

    if (pencilExtensions.length > 0) {
      return { installed: true, extensions: pencilExtensions, path: extensionsPath };
    } else {
      return { installed: false, extensions: [], path: extensionsPath };
    }
  } catch (error) {
    console.error('检测 Pencil 扩展时出错:', error.message);
    process.exit(2);
  }
}

/**
 * 主检测函数
 */
function main() {
  console.log('检测 Pencil 环境状态...\n');

  // 1. 检测 VSCode 扩展
  console.log('【1/2】检测 VSCode Pencil 扩展...');
  const extensionResult = checkPencilExtension();

  if (extensionResult.installed) {
    console.log('  ✓ VSCode Pencil 扩展已安装');
    console.log(`    扩展路径: ${extensionResult.path}`);
    extensionResult.extensions.forEach(ext => console.log(`    - ${ext}`));
  } else {
    console.log('  ✗ VSCode Pencil 扩展未安装');
    console.log(`    扩展目录: ${extensionResult.path}`);
    console.log('\n建议：请先在 VSCode 中安装 Pencil 扩展');
    process.exit(1);
  }

  console.log('');

  // 2. 检测 MCP 服务器配置
  console.log('【2/2】检测 Pencil MCP 服务器配置...');
  const mcpResult = checkPencilMcpConfig();

  if (mcpResult.found) {
    console.log('  ✓ Pencil MCP 服务器配置已找到');
    console.log(`    配置文件: ${mcpResult.configPath}`);
    if (mcpResult.key) {
      console.log(`    配置键名: ${mcpResult.key}`);
    }
    console.log('\n【结论】Pencil 环境检测完成 ✓');
    console.log('  - VSCode 扩展: 已安装');
    console.log('  - MCP 配置: 已配置');
    console.log('\n注意：MCP 服务器需要在 VSCode 扩展中启动才能生效。');
    process.exit(0);
  } else {
    console.log('  ⚠ Pencil MCP 服务器配置未找到');
    console.log('\n【结论】检测到潜在问题 ⚠');
    console.log('  - VSCode 扩展: 已安装 ✓');
    console.log('  - MCP 配置: 未配置 ✗');
    console.log('\n可能的原因：');
    console.log('  1. Claude Code 配置文件中未添加 Pencil MCP 服务器');
    console.log('  2. MCP 服务器配置名称不是 "pencil"');
    console.log('  3. Pencil 扩展需要在 VSCode 中启动 MCP 服务器');
    console.log('\n建议操作：');
    console.log('  1. 在 VSCode 中打开 Pencil 扩展');
    console.log('  2. 确保扩展的 MCP 服务器已启动');
    console.log('  3. 或在 Claude Code 配置中手动添加 Pencil MCP 服务器');
    process.exit(3);
  }
}

// 执行检测
main();
