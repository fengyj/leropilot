# Git 安装策略

## 设计原则

1. **优先使用系统 Git**（如果已安装）
2. **程序目录备选**（如果系统没有）
3. **不需要 sudo 权限**
4. **所有平台一致的逻辑**

## 检测逻辑

```python
async def ensure_git() -> Path:
    """确保 Git 可用"""
    # 1. 检测系统 Git
    system_git = await check_system_git()
    if system_git:
        return system_git

    # 2. 检测程序目录 Git
    bundled_git = await check_bundled_git()
    if bundled_git:
        return bundled_git

    # 3. 下载到程序目录
    return await install_git_to_program_dir()
```

## 平台实现

### Windows

**策略**: 下载 Git Portable

**下载源**:

- https://github.com/git-for-windows/git/releases
- 文件: `PortableGit-{version}-64-bit.7z.exe`

**目录结构**:

```
{data_dir}/tools/
  └── git-2.43.0/
      ├── bin/
      │   └── git.exe
      ├── cmd/
      └── mingw64/
```

### macOS

**策略**: 检测系统 → 下载静态构建

#### 检测系统 Git

```bash
# 检查 Xcode Command Line Tools 的 Git
which git
# /usr/bin/git 或 /Library/Developer/CommandLineTools/usr/bin/git

# 检查 Homebrew 的 Git
/opt/homebrew/bin/git --version  # Apple Silicon
/usr/local/bin/git --version     # Intel
```

#### 下载静态构建

**下载源**:

- https://sourceforge.net/projects/git-osx-installer/files/
- 文件: `git-{version}-intel-universal-mavericks.dmg`

**或者使用预编译二进制**:

- https://git-scm.com/download/mac
- 提取 `/usr/local/git/bin/git`

**目录结构**:

```
{data_dir}/tools/
  └── git-2.43.0/
      └── bin/
          └── git
```

### Linux

**策略**: 检测系统 → 下载静态构建

#### 检测系统 Git

```bash
which git
# /usr/bin/git
```

#### 下载静态构建

**下载源**:

- https://mirrors.edge.kernel.org/pub/software/scm/git/
- 文件: `git-{version}.tar.gz`

**或者使用预编译二进制**:

- https://github.com/git/git/releases
- 下载对应架构的二进制

**目录结构**:

```
{data_dir}/tools/
  └── git-2.43.0/
      └── bin/
          └── git
```

## 实现代码

### GitManager

```python
class GitManager:
    """Git 安装和管理"""

    DEFAULT_VERSION = "2.43.0"

    async def ensure_git(self) -> Path:
        """确保 Git 可用"""
        # 1. 检测系统 Git
        system_git = await self.check_system_git()
        if system_git:
            logger.info(f"Using system Git: {system_git}")
            return system_git

        # 2. 检测程序目录 Git
        bundled_git = await self.check_bundled_git()
        if bundled_git:
            logger.info(f"Using bundled Git: {bundled_git}")
            return bundled_git

        # 3. 下载到程序目录
        logger.info("Git not found, downloading...")
        return await self.install_git(self.DEFAULT_VERSION)

    async def check_system_git(self) -> Optional[Path]:
        """检测系统 Git"""
        try:
            # 使用 which/where 查找
            if platform.system() == "Windows":
                result = await run_command(["where", "git"], capture_output=True)
            else:
                result = await run_command(["which", "git"], capture_output=True)

            git_path = Path(result.stdout.strip().split('\n')[0])

            # 验证版本
            version_output = await run_command([str(git_path), "--version"], capture_output=True)
            if "git version" in version_output:
                return git_path
        except Exception:
            pass

        return None

    async def check_bundled_git(self) -> Optional[Path]:
        """检测程序目录 Git"""
        tools_dir = self.config.paths.data_dir / "tools"

        # 查找所有 git-* 目录
        for git_dir in sorted(tools_dir.glob("git-*"), reverse=True):
            git_bin = git_dir / "bin" / "git"
            if platform.system() == "Windows":
                git_bin = git_bin.with_suffix(".exe")

            if git_bin.exists():
                return git_bin

        return None

    async def install_git(self, version: str) -> Path:
        """安装 Git 到程序目录"""
        platform_name = platform.system().lower()
        target_dir = self.config.paths.data_dir / "tools" / f"git-{version}"

        if target_dir.exists():
            git_bin = target_dir / "bin" / "git"
            if platform_name == "windows":
                git_bin = git_bin.with_suffix(".exe")
            return git_bin

        if platform_name == "windows":
            return await self._install_windows(target_dir, version)
        elif platform_name == "darwin":
            return await self._install_macos(target_dir, version)
        else:
            return await self._install_linux(target_dir, version)

    async def _install_windows(self, target_dir: Path, version: str) -> Path:
        """Windows: 下载 Git Portable"""
        # 下载 PortableGit
        url = f"https://github.com/git-for-windows/git/releases/download/v{version}.windows.1/PortableGit-{version}-64-bit.7z.exe"

        archive_file = await download_file(url, target_dir.parent / "git.7z.exe")

        # 解压（自解压文件）
        await run_command([str(archive_file), "-o", str(target_dir), "-y"])

        # 清理
        archive_file.unlink()

        return target_dir / "bin" / "git.exe"

    async def _install_macos(self, target_dir: Path, version: str) -> Path:
        """macOS: 下载预编译二进制"""
        # 从 git-scm.com 下载
        url = f"https://sourceforge.net/projects/git-osx-installer/files/git-{version}-intel-universal-mavericks.dmg/download"

        dmg_file = await download_file(url, target_dir.parent / "git.dmg")

        # 挂载 DMG
        mount_point = target_dir.parent / "git_mount"
        await run_command(["hdiutil", "attach", str(dmg_file), "-mountpoint", str(mount_point)])

        # 提取 Git 二进制
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "bin").mkdir(exist_ok=True)

        # 复制文件
        shutil.copy(
            mount_point / "usr" / "local" / "git" / "bin" / "git",
            target_dir / "bin" / "git"
        )

        # 卸载 DMG
        await run_command(["hdiutil", "detach", str(mount_point)])

        # 清理
        dmg_file.unlink()

        return target_dir / "bin" / "git"

    async def _install_linux(self, target_dir: Path, version: str) -> Path:
        """Linux: 下载静态构建"""
        # 从 kernel.org 下载
        url = f"https://mirrors.edge.kernel.org/pub/software/scm/git/git-{version}.tar.gz"

        tar_file = await download_file(url, target_dir.parent / "git.tar.gz")

        # 解压
        await extract_tar(tar_file, target_dir.parent / "temp")

        # 编译（静态链接）
        build_dir = target_dir.parent / "temp" / f"git-{version}"
        await run_command(
            ["make", "prefix=/usr", "NO_TCLTK=YesPlease", "NO_GETTEXT=YesPlease"],
            cwd=build_dir
        )
        await run_command(
            ["make", "install", f"prefix={target_dir}"],
            cwd=build_dir
        )

        # 清理
        tar_file.unlink()
        shutil.rmtree(target_dir.parent / "temp")

        return target_dir / "bin" / "git"
```

## UI 提示

### 下载 Git

```
┌─────────────────────────────────────────┐
│ 需要下载 Git                            │
├─────────────────────────────────────────┤
│                                         │
│ 系统未检测到 Git                        │
│                                         │
│ 将下载 Git 到程序目录:                  │
│ ~/.leropilot/tools/git-2.43.0/          │
│                                         │
│ 下载大小: ~45 MB (Windows)              │
│           ~20 MB (macOS/Linux)          │
│                                         │
│ ✓ 无需管理员权限                        │
│ ✓ 不影响系统 Git                        │
│                                         │
│     [开始下载]  [取消]                  │
└─────────────────────────────────────────┘
```

## 总结

### 优势

- ✅ **无需 sudo**: 所有平台都可以下载到程序目录
- ✅ **优先系统**: 如果系统有 Git，优先使用
- ✅ **完全自动化**: 用户无需手动安装
- ✅ **版本控制**: 程序目录的 Git 版本可控

### 与其他工具一致

- UV: 打包内置
- Git: 检测系统 → 程序目录
- FFmpeg: 程序目录
- Python: UV 自动下载

**所有工具都不需要 sudo！**
