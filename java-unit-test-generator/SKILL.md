---
name: java-unit-test-generator
version: "1.1.0"
description: |
  当用户要求为 Java Spring Boot Service 层类（ServiceImpl）生成、创建或编写单元测试时使用。
  触发词："generate tests"、"generate unit tests"、"单元测试"、"生成测试"、"批量生成测试"、
  "/generate-tests"、"/java-unit-test-generator"、"test coverage"、"给XXX写测试"、"给XXX模块生成单元测试"。
  支持单类、单模块或整个项目的批量生成。
  专用于使用 MyBatis、@Resource/@Autowired 依赖注入、WphResponseResult/ResponseMessage 响应包装类的遗留 Spring Boot 项目。
  当用户提到 Java 服务类的单元测试、测试生成或测试覆盖率时，务必使用此 Skill。
allowed-tools: Read, Write, Glob, Grep, Bash, AskUserQuestion
---

# Java Spring Boot Service 层单元测试生成器

为 Spring Boot ServiceImpl 类生成 JUnit 5 + Mockito 单元测试。专为使用 MyBatis Mapper、手动事务管理、静态方法调用的遗留项目设计。

## 范围选择

被调用时，根据用户输入确定生成范围：

| 范围 | 输入模式 | 行为 |
|------|---------|------|
| 单个类 | 文件路径或类名 | 分析一个 ServiceImpl，生成一个测试文件 |
| 单个模块 | 模块名（如 `core`、`jkfw`、`mzfw`） | 扫描模块下所有 ServiceImpl，生成测试文件 |
| 整个项目 | `all`、`project` 或无明确目标 | 扫描所有模块，为每个 ServiceImpl 生成测试 |

**批处理规则**：模块/项目模式下，逐类顺序处理。生成每个测试文件后，验证编译通过再处理下一个。

---

## Phase 1: 上下文发现

### 1.1 读取项目配置

读取以下文件了解项目：

- `CLAUDE.md` — 项目约定、构建命令
- `pom.xml`（父 POM + 相关模块）— 依赖、Java 版本

识别：
- Java 编译版本（1.8、11、17）
- Spring Boot 版本
- Mockito 版本（必须 4.x 以支持现代特性）
- `spring-boot-starter-test` 是否存在于 test scope

### 1.2 查找已有测试模式

搜索已有测试文件：

```bash
find <module>/src/test -name "*Test.java" -type f
```

如果已有测试，读取 2-3 个识别既有模式：
- 导入约定
- 断言风格（AssertJ 还是 JUnit assertions）
- 辅助工具类（如 `ServiceTestHelper`）
- @DisplayName 语言（中文或英文）
- @Nested 分组风格

### 1.3 检查测试辅助工具

搜索测试工具类：

```bash
find <module>/src/test -name "*Helper*.java" -o -name "*Util*.java" -type f
```

如果存在 `ServiceTestHelper` 等工具类，**读取并在生成的测试中复用其方法**。

---

## Phase 2: 源码分析（逐类处理）

对每个 ServiceImpl 类：

### 2.1 读取 ServiceImpl 源码

读取完整源文件，提取：
- 包声明
- 类名
- 所有字段声明（类型和注入注解：@Resource、@Autowired）
- 所有 public/protected 方法及完整签名

### 2.2 读取依赖源码（关键步骤）

对每个依赖字段（Mapper、Service、DataManager 等）：

- **Mapper 接口**：读取 Mapper Java 接口获取**精确的方法签名**。绝不能猜测 Mapper 方法名或参数数量/类型。这是测试编译失败的首要原因。
- **Service 接口**：读取以了解方法约定和返回类型。
- **DataManager / EnvManager**：作为配置提供者。`getConfigValue(orgnCode, paramKey)` 和 `getConfigValues(orgnCode, paramKey)` 是最常见的模式。
- **Feign 客户端**：读取接口获取返回类型。

### 2.3 读取领域类

对每个作为方法参数或返回类型使用的 DTO/DO/VO，读取类以识别：
- 可用的 setter（用于构建测试数据）
- 可用的 getter（用于断言）
- 是否使用了 Lombok @Data/@Getter/@Setter

### 2.4 方法分类

对每个方法，分为以下三类之一：

**A 类：可测试**（纯逻辑，依赖可 Mock）
- 无不可 Mock 类的静态方法调用
- 无手动事务管理
- 标准 mock-return-test 模式

**B 类：部分可测试**（需要变通处理）
- 使用静态工具方法如 `IdUtils.getDjh()` — 可测试输出存在但无法验证精确值
- 使用 `DataManager.getConfigValue()` — Mock DataManager
- 使用编程式 `DataSourceTransactionManager` — 使用反射注入模式

**C 类：不可测试**（跳过并记录）
- 调用 `PageHelper.startPage()` — static final 方法
- 调用 `TransactionAspectSupport.currentTransactionStatus()` — static 方法
- 使用 `DataSourceTransactionManager.getTransaction()` 的复杂事务逻辑
- Mockito 无法覆盖的 `final` 方法

**决策流程图：**

```
方法包含不可测试的静态调用？
  是 → C 类，加入跳过列表
  否 → 方法使用手动事务？
    是 → 能 Mock DataSource 处理基本流程吗？
      是 → B 类
      否 → C 类
    否 → A 类
```

对 C 类方法，在测试类顶部添加注释块：

```java
/**
 * 跳过的方法（不可测试）:
 * <ul>
 *   <li>methodName (原因: PageHelper.startPage 静态方法)</li>
 *   <li>methodName (原因: TransactionAspectSupport 静态方法)</li>
 * </ul>
 */
```

### 2.5 检查已有测试

搜索已有测试文件。如果找到：
- 完整读取
- 仅生成未覆盖方法的 @Nested 类
- 询问用户是追加还是覆盖

---

## Phase 3: 测试生成

### 3.1 测试文件模板

```java
package ${service.package};

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
// ... 按需导入领域类

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("${service.description}")
class ${service.className}Test {

    // 为 ServiceImpl 中的每个依赖字段声明一个 @Mock
    @Mock
    private ${DependencyType} ${dependencyName};
    // ...

    @InjectMocks
    private ${service.className} ${service.fieldName};

    // 按方法分组的嵌套测试类
    ${nestedTestClasses}

    // 底部的辅助方法
    ${helperMethods}
}
```

### 3.2 Mock 声明规则

- 为 ServiceImpl 中的**每个**依赖字段声明一个 `@Mock` 字段
- 精确匹配字段类型（Mapper 接口类型，而非实现类）
- `@Resource` 注入：测试中的字段名必须与源码完全一致（Mockito 按名称匹配）
- B 类方法中的 `DataSourceTransactionManager`：通过 `@BeforeEach` + 反射构造真实实例并注入 mock DataSource
- Mock 字段顺序与源文件一致

### 3.3 嵌套测试类模式

使用 @Nested 按方法分组：

```java
@Nested
@DisplayName("${methodName} - ${methodDescription}")
class ${MethodName}Test {

    @Test
    @DisplayName("${场景描述，使用中文}")
    void ${methodName}_${scenario}_${outcome}() {
        // Given - 设置 Mock 和测试数据
        // When - 调用方法
        // Then - 断言结果
    }
}
```

### 3.4 @DisplayName 规则

- 所有 @DisplayName 注解使用**中文**
- 类级别：业务领域（如 `@DisplayName("挂号信息保存服务")`）
- 嵌套类：方法 + 用途（如 `@DisplayName("getMzHzrqxx - 获取门诊患者人群信息")`）
- 测试方法：场景描述（如 `@DisplayName("正常场景-返回挂号次数")`）

### 3.5 断言模式

**WphResponseResult 响应**（存在 ServiceTestHelper 时）：

```java
assertSuccess(result);
assertFail(result, "expected error keyword");
assertSuccessWithData(result, expectedData);
```

**WphResponseResult 响应**（无辅助工具时）：

```java
assertEquals("T", result.getCode());
assertEquals("F", result.getCode());
assertTrue(result.getMessage().contains("keyword"));
```

**注意**：检查实际的响应包装类。常见变体：
- `WphResponseResult<T>` — code "T"/"F"，数据在 `result` 字段
- `ResponseMessage<T>` — code "T"/"F"，数据在 `data` 字段
- `WphResponseMessage<T>` — 较新变体，需检查实际字段名

**普通返回值：**

```java
assertEquals(expected, actual);
assertNotNull(actual);
assertThrows(SomeException.class, () -> service.method(args));
```

**无返回值的方法（通过副作用验证）：**

```java
verify(mapper).insertSomething(argThat(x -> {
    assertEquals("expected", x.getField());
    return true;
}));
```

### 3.6 测试数据构建

在测试类底部使用辅助方法：

```java
private ${DtoType} build${DtoName}() {
    ${DtoType} dto = new ${DtoType}();
    dto.setField1(value1);
    dto.setField2(value2);
    return dto;
}
```

### 3.7 覆盖率要求

对每个可测试方法：

| 分类 | 是否必需 | 数量 |
|------|---------|------|
| 正常路径 | 必需 | 1 |
| 空/null 输入 | 必需 | 1-2 |
| 边界条件 | 视情况 | 1-2 |
| 异常/错误 | 必需 | 1 |
| 业务规则分支 | 视情况 | 1-3 |

目标：每个方法 **3-8 个测试用例**。

---

## Phase 4: 验证

### 4.1 创建测试目录

```bash
mkdir -p ${module}/src/test/java/${packagePath}
```

### 4.2 写入测试文件

输出路径：`${module}/src/test/java/${package}/${ClassName}Test.java`

### 4.3 编译

```bash
cd ${projectRoot}
mvn test-compile -pl ${module} -am -q
```

编译失败时（最多修复 5 次）：
- 修复导入问题
- 修复类型不匹配（Mapper 方法签名不匹配）
- 修复缺少的方法或参数数量错误

### 4.4 执行测试

```bash
cd ${projectRoot}
mvn test -pl ${module} -Dtest=${ClassName}Test -am
```

测试失败时：
- 分析失败信息
- 修复 Mock 设置或断言
- 重新运行直到全部通过
- 如果修复 3 次后仍失败，**删除该测试**并告知用户

### 4.5 报告

```
Generated: ${ClassName}Test.java
  已测试方法: ${count} / ${total}
  跳过方法（不可测试）: ${list}
  测试用例数: ${testCaseCount}
  编译: PASS
  执行: ${passCount} passed
```

---

## Phase 5: 批量模式

模块或项目范围：

### 5.1 模块发现（通过 pom.xml 递归解析）

从项目根目录开始，递归解析 `pom.xml` 的 `<modules>` 构建完整模块树，支持任意层级嵌套。

**解析规则**：

1. 读取根 `pom.xml`，提取 `<modules>` 下的所有 `<module>` 子元素
2. 对每个子模块，进入对应目录读取其 `pom.xml`，继续递归解析
3. 如果某个 `pom.xml` 没有 `<modules>`，则为叶子模块（包含实际源码）
4. 过滤掉 `<packaging>pom</packaging>` 的纯聚合模块（无 src 目录）

**解析脚本**：

```bash
# 递归解析模块树，输出所有叶子模块路径
parse_modules() {
  local pom_file="$1/pom.xml"
  if [ ! -f "$pom_file" ]; then return; fi

  # 提取 <modules> 下的 <module> 值
  local modules=$(grep -A 100 '<modules>' "$pom_file" | grep -oP '<module>\K[^<]+' | head -20)

  if [ -z "$modules" ]; then
    # 无子模块，判断是否为叶子模块（有 src/main/java 目录）
    if [ -d "$1/src/main/java" ]; then
      echo "$1"
    fi
    return
  fi

  for mod in $modules; do
    parse_modules "$1/$mod"
  done
}

# 从项目根目录开始解析
parse_modules "${projectRoot}"
```

**多级模块示例**：

```
项目根 pom.xml
├── core/                     # 叶子模块，有 ServiceImpl
├── jkfw/                     # 聚合模块，<packaging>pom</packaging>
│   ├── jkfw-api/             # 叶子模块，无 ServiceImpl
│   └── jkfw-service/         # 叶子模块，有 ServiceImpl
├── mzfw/                     # 聚合模块
│   ├── mzfw-registration/    # 叶子模块，有 ServiceImpl
│   └── mzfw-pharmacy/        # 叶子模块，有 ServiceImpl
└── common/                   # 叶子模块，工具类，无 ServiceImpl
```

解析结果：`core`, `jkfw/jkfw-service`, `mzfw/mzfw-registration`, `mzfw/mzfw-pharmacy`, `common`

**模块下查找 Service 实现类**：

采用多层识别策略，先粗筛再精确确认：

```bash
# Step 1: 按包路径和文件名模式粗筛
# 匹配 service/impl/manager/manager.impl 包下的类
find ${modulePath}/src/main/java -type f -name "*.java" \
  -regex ".*/\(service/impl\|service\|manager/impl\|manager\)/[^/]*\.java"

# Step 2: 在粗筛结果中，通过注解和接口实现精确确认
# 识别带有 @Service、@Component、@Transactional 注解的类
# 识别 implements XxxService 接口的类
```

**Service 实现类识别规则**（满足任一条件即纳入）：

| 识别方式 | 匹配规则 | 示例 |
|---------|---------|------|
| 文件名模式 | `*ServiceImpl.java`、`*ManagerImpl.java` | `UserServiceImpl.java` |
| `@Service` 注解 | 类声明上有 `@Service` | `@Service public class UserService {}` |
| `@Component` 注解 | 类声明上有 `@Component` 且在 service 包下 | `@Component public class OrderHandler {}` |
| `@Transactional` 注解 | 类声明上有 `@Transactional` 且在 service/manager 包下 | `@Transactional public class PaymentManager {}` |
| 实现 Service 接口 | `implements XxxService` 或 `implements XxxManager` | `class UserServiceImpl implements UserService` |

**排除规则**：
- 抽象类（`abstract class`）
- 接口本身（`interface`）
- 基类/通用类（类名含 `Base`、`Abstract`、`Common`、`Generic`、`Util`）

### 5.2 扫描与分类

1. 通过 5.1 获取所有叶子模块列表
2. 在每个叶子模块下，按上述识别规则查找 Service 实现类
3. 过滤掉抽象类/基类/接口
4. 按模块对 Service 实现类分组，确定并行策略
5. 记录每个类的完整路径和所属模块路径（用于 `-pl` 参数）

### 5.3 执行策略

根据 ServiceImpl 数量选择执行策略：

| ServiceImpl 数量 | 策略 | 说明 |
|-----------------|------|------|
| ≤ 5 | 串行处理 | 逐类顺序执行 Phase 2 → Phase 4 |
| > 5 | **并行处理** | 使用 subagent 并行生成，提升效率 |

**串行处理**（≤ 5 个类）：
- 逐类执行 Phase 2 → Phase 4
- 修复并验证后再处理下一个

**并行处理**（> 5 个类）：
- 使用 `subagent_type: "general-purpose"` 的 Agent 并行派发任务
- **最大并发数：3**（受大模型 API 并发限制，同时运行的 Agent 不超过 3 个）
- **按模块分组派发**：每个模块作为一个 Agent 任务，模块内的类串行处理
- 每个 Agent 内部完整执行 Phase 2 → Phase 4
- 如果模块数 > 3，分批执行：先派发 3 个 Agent，完成后派发下一批
- Agent 完成后主会话汇总所有结果

**并行分组策略**：
- 优先按**一级模块**分组（如 core、jkfw、mzfw 各一个 Agent）
- 如果一级模块过多，按叶子模块分组
- 同一模块内的多个类串行编译验证，避免锁文件冲突
- 每批最多 3 个 Agent 并行，批次间串行等待
- 不同模块之间完全并行，互不影响

**并行 Agent prompt 模板**：

```
为 ${module} 模块生成 JUnit 5 单元测试。

项目根目录: ${projectRoot}
模块路径: ${modulePath}
模块下待处理的 ServiceImpl 列表:
  - ${filePath1}
  - ${filePath2}
  - ...

请对每个 ServiceImpl 串行执行以下步骤：
1. 读取 ServiceImpl 源码和所有依赖（Mapper 接口、DTO/DO）
2. 分析方法并分类（A/B/C 类）
3. 生成测试文件到 ${modulePath}/src/test/java/${packagePath}/${ClassName}Test.java
4. 编译验证：mvn test-compile -pl ${modulePath} -am -q
5. 执行测试：mvn test -pl ${modulePath} -Dtest=${ClassName}Test -am
6. 修复编译/测试失败（编译最多 5 次，测试修复最多 3 次）
7. 处理完一个类后再处理下一个
8. 最终输出该模块的结果报告
```

### 5.4 最终汇总

```
模块发现: 从 pom.xml 递归解析，共 ${moduleCount} 个叶子模块
模块树:
  ${moduleTree}

ServiceImpl 总数: ${N}
生成测试: ${M}
已存在测试: ${K}
编译通过: ${P}
全部测试通过: ${T}
执行策略: ${串行/并行，并行时注明并发数}
总耗时: ${duration}
```

---

## 禁止模式

- 绝不使用 `@SpringBootTest` — 这些是单元测试
- 绝不使用 `@MockBean` — 使用 Mockito 的 `@Mock`
- 绝不在测试类中使用 `@Autowired` — 使用 `@InjectMocks`
- 绝不猜测 Mapper 方法签名 — 始终读取 Mapper 接口
- 绝不为 private 方法生成测试 — 通过 public API 测试
- 绝不使用 `Thread.sleep()` 或基于超时的断言
- 绝不跳过编译验证
- 绝不在当前测试编译失败时处理下一个类

---

## 项目适配

在新项目上使用此 Skill 时，识别以下内容：

1. **响应包装类**：搜索 `ResponseResult`、`ResponseMessage`、`Result<T>`，识别成功/失败码。
2. **依赖注入注解**：检查 `@Resource` 还是 `@Autowired`。
3. **配置提供者**：系统参数如何读取（DataManager、@Value、Environment）。
4. **数据访问层**：MyBatis Mapper 还是 JPA Repository 还是 JDBC Template。
5. **测试依赖**：确保 `spring-boot-starter-test` 和 `mockito-core` 存在。

### 常见响应包装类

| 类型 | 成功 | 失败 | 数据字段 |
|------|------|------|---------|
| `WphResponseResult<T>` | `"T"` | `"F"` | `result` |
| `ResponseMessage<T>` | `"T"` | `"F"` | `data` |

### 测试依赖

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-test</artifactId>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.mockito</groupId>
    <artifactId>mockito-core</artifactId>
    <version>4.5.1</version>
    <scope>test</scope>
</dependency>
```

---

## 扫描命令速查

```bash
# 查找模块下所有 ServiceImpl
find <module>/src/main/java -name "*ServiceImpl.java"

# 查找项目下所有 ServiceImpl
find . -name "*ServiceImpl.java" -path "*/src/main/java/*"

# 检查已有测试
find <module>/src/test -name "*Test.java"

# 编译
mvn test-compile -pl <module> -am -q

# 运行单个测试
mvn test -pl <module> -Dtest=ClassNameTest
```
