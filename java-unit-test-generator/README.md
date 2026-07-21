# Java 单元测试生成器

Claude Code Skill — 自动为 Spring Boot ServiceImpl 类生成 JUnit 5 + Mockito 单元测试。


## 功能特性

- **灵活范围**：支持单类、单模块、整个项目批量生成
- **智能分析**：自动读取源码、依赖接口（Mapper/Service）、DTO/DO 类，精确生成测试代码
- **方法分类**：将方法分为可测试（A）、部分可测试（B）、不可测试（C）三类，跳过无法测试的方法并记录原因
- **编译验证**：生成后自动编译并执行测试，失败时自动修复
- **中文 DisplayName**：测试类和方法的 `@DisplayName` 使用中文描述，便于阅读
- **项目适配**：自动识别项目中的响应包装类、DI 注入方式、配置读取方式

## 使用方式

### 触发方式

在 Claude Code 中使用以下任意方式触发：

```
# 斜杠命令
/generate-tests
/java-unit-test-generator

# 自然语言
给 XXServiceImpl 写单元测试
给 core 模块批量生成测试
生成整个项目的单元测试
```

### 生成范围

| 范围 | 输入示例 | 行为 |
|------|---------|------|
| 单个类 | 文件路径或类名 | 分析一个 ServiceImpl，生成一个测试文件 |
| 单个模块 | 模块名如 `core`、`jkfw` | 扫描模块下所有 ServiceImpl，逐一生成 |
| 整个项目 | `all`、`project` | 扫描所有模块，为每个 ServiceImpl 生成测试 |

## 工作流程

```
Phase 1: 上下文发现
  ├── 读取项目配置（pom.xml、CLAUDE.md）
  ├── 查找已有测试模式
  └── 检查测试辅助工具（如 ServiceTestHelper）

Phase 2: 源码分析（逐类处理）
  ├── 读取 ServiceImpl 源码，提取字段和方法签名
  ├── 读取依赖源码（Mapper 接口、Service 接口、DTO/DO）
  ├── 方法分类（A/B/C）
  └── 检查是否已有测试文件

Phase 3: 测试生成
  ├── @Mock 声明（与源码字段一一对应，顺序一致）
  ├── @Nested 分组（按方法分组）
  ├── 断言模式（适配项目的响应包装类）
  └── 测试数据构建辅助方法

Phase 4: 验证
  ├── 编译检查（mvn test-compile，最多修复 5 次）
  ├── 执行测试（mvn test，最多修复 3 次）
  └── 输出报告（测试方法数、跳过方法、用例数、编译/执行结果）

Phase 5: 批量模式
  └── 逐类处理，当前类验证通过后再处理下一个
```

## 生成示例

```java
@ExtendWith(MockitoExtension.class)
@DisplayName("库存冻结服务")
class MedFreezeServiceImplTest {

    @Mock
    private MedFreezeMapper medFreezeMapper;

    @Mock
    private DataManager dataManager;

    @InjectMocks
    private MedFreezeServiceImpl medFreezeService;

    @Nested
    @DisplayName("medFreeze - 库存冻结")
    class MedFreezeTest {

        @Test
        @DisplayName("正常场景-冻结成功")
        void medFreeze_normal_success() {
            // Given
            MedFreezeDTO dto = buildFreezeDTO("ORG001", "1");
            when(medFreezeMapper.selectByCondition(any())).thenReturn(buildMedInfoList());

            // When
            WphResponseResult<List<MedFreezeResDTO>> result = medFreezeService.medFreeze(dto);

            // Then
            assertEquals("T", result.getCode());
        }

        @Test
        @DisplayName("明细为空-返回失败")
        void medFreeze_emptyDetails_fail() {
            MedFreezeDTO dto = new MedFreezeDTO();
            dto.setDetails(Collections.emptyList());

            WphResponseResult<List<MedFreezeResDTO>> result = medFreezeService.medFreeze(dto);

            assertEquals("F", result.getCode());
            assertTrue(result.getMessage().contains("冻结明细为空"));
        }
    }

    private MedFreezeDTO buildFreezeDTO(String orgnCode, String djlx) {
        MedFreezeDTO dto = new MedFreezeDTO();
        dto.setOrgnCode(orgnCode);
        dto.setDjlx(djlx);
        return dto;
    }
}
```

## 方法分类策略

| 分类 | 说明 | 处理方式 |
|------|------|---------|
| **A - 可测试** | 纯逻辑，依赖可 Mock | 标准生成，覆盖正常/异常/边界场景 |
| **B - 部分可测试** | 含静态工具方法或编程式事务 | 反射注入 TransactionManager，跳过不可控部分 |
| **C - 不可测试** | PageHelper、TransactionAspectSupport 等 | 跳过并在测试类顶部注释说明原因 |

每个可测试方法生成 3-8 个测试用例，覆盖正常路径、空输入、边界条件、异常场景和业务分支。

## 支持的响应包装类

| 类型 | 成功码 | 失败码 | 数据字段 |
|------|-------|-------|---------|
| `WphResponseResult<T>` | `"T"` | `"F"` | `result` |
| `ResponseMessage<T>` | `"T"` | `"F"` | `data` |
| `WphResponseMessage<T>` | `"T"` | `"F"` | 需检查实际字段名 |

如果项目中存在 `ServiceTestHelper`，会优先使用其断言方法（`assertSuccess`、`assertFail`、`assertSuccessWithData`）。

## 技术栈要求

- Java 8/11/17
- Spring Boot（任意版本）
- MyBatis Mapper 接口
- JUnit 5 + Mockito 4.x
- `spring-boot-starter-test`（test scope）

## 项目结构

```
java-unit-test-generator/
├── SKILL.md                    # Skill 定义文件（核心逻辑与规则）
├── references/
│   └── bathis-examples.md      # 从 583 个通过测试中提取的参考模式
└── README.md
```

## 禁止模式

生成测试严格遵守以下规则：

- 不使用 `@SpringBootTest`（纯单元测试，不启动 Spring 容器）
- 不使用 `@MockBean`（使用 Mockito 的 `@Mock`）
- 不使用 `@Autowired`（使用 `@InjectMocks`）
- 不猜测 Mapper 方法签名（始终读取 Mapper 接口源码）
- 不为 private 方法生成测试（通过 public API 间接测试）
- 不跳过编译验证（每个测试文件必须编译通过）
