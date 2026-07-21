# Bathis 项目单元测试示例和模式

从 583 个已通过的单元测试中提取的典型模式，供生成测试时参考。

## 1. 响应包装类断言

### WphResponseResult (新版)

```java
// code="T" 成功, code="F" 失败, 数据在 result 字段
WphResponseResult<List<MedFreezeResDTO>> result = service.medFreeze(dto);
assertEquals("T", result.getCode());
assertEquals("F", result.getCode());
assertTrue(result.getMessage().contains("冻结明细为空"));
```

### ResponseMessage (旧版)

```java
// code="T" 成功, code="F" 失败, 数据在 data 字段
ResponseMessage<String> response = new ResponseMessage<>();
response.setCode("T");
response.setData("value");
```

### ServiceTestHelper 工具类

```java
import static com.winning.bathis.core.service.ServiceTestHelper.*;

assertSuccess(result);                          // code="T"
assertFail(result, "错误关键字");                // code="F" + message 包含关键字
assertSuccessWithData(result, expectedData);     // code="T" + data 匹配
assertSuccessNotNull(result);                   // code="T" + data 非空
```

## 2. DataManager 配置 Mock 模式

### 单个配置值

```java
when(dataManager.getConfigValue(eq("ORG001"), eq("A063"))).thenReturn("否");
```

### 批量配置值（JSONObject）

```java
JSONObject configJson = new JSONObject();
configJson.put("A023", "");
configJson.put("A024", "");
configJson.put("C161", "是");
configJson.put("C167", "");
when(dataManager.getConfigValues(any(), anyString())).thenReturn(configJson);
```

### lenient() 用于可能未被调用的配置

```java
lenient().when(dataManager.getConfigValue(eq("ORG001"), anyString())).thenReturn("1");
```

## 3. TransactionManager 反射注入模式

当 ServiceImpl 使用 `DataSourceTransactionManager` 的编程式事务时：

```java
private DataSourceTransactionManager transactionManager;

@BeforeEach
void setUp() throws Exception {
    javax.sql.DataSource mockDs = mock(javax.sql.DataSource.class);
    java.sql.Connection mockConn = mock(java.sql.Connection.class);
    lenient().when(mockDs.getConnection()).thenReturn(mockConn);
    transactionManager = new DataSourceTransactionManager(mockDs);
    transactionManager.afterPropertiesSet();
    java.lang.reflect.Field tmField = ServiceImpl.class.getDeclaredField("transactionManager");
    tmField.setAccessible(true);
    tmField.set(serviceInstance, transactionManager);
}
```

**限制**：`getTransaction()`、`commit()`、`rollback()` 是 final 方法，无法通过 Mockito 拦截。只能测试不依赖事务语义的逻辑分支。

## 4. @Nested + @DisplayName 中文命名风格

```java
@Nested
@DisplayName("medFreeze - 库存冻结")
class MedFreezeTest {

    @Test
    @DisplayName("明细为空 - 返回失败")
    void emptyDetails_returnsFail() {
        // ...
    }

    @Test
    @DisplayName("药品信息查询为空 - 返回失败")
    void noMedInfo_returnsFail() {
        // ...
    }
}
```

## 5. 跳过不可测方法的注释模板

```java
/**
 * 跳过的方法（不可测试）:
 * <ul>
 *   <li>saveByCis (原因: DataSourceTransactionManager final 方法)</li>
 *   <li>saveRegistration (原因: PageHelper.startPage 静态方法)</li>
 *   <li>editRegistration (原因: TransactionAspectSupport 静态方法)</li>
 * </ul>
 */
```

## 6. 典型测试数据构建方法

```java
private MedFreezeDTO buildFreezeDTO(String orgnCode, String djlx) {
    MedFreezeDTO dto = new MedFreezeDTO();
    dto.setOrgnCode(orgnCode);
    dto.setDjlx(djlx);
    MedFreezeDetail detail = new MedFreezeDetail();
    detail.setYfdm("YF001");
    detail.setYpdm("YP001");
    detail.setYpsl(new BigDecimal("10"));
    detail.setZhxs(new BigDecimal("1"));
    dto.setDetails(new ArrayList<>(Collections.singletonList(detail)));
    return dto;
}
```

## 7. 常量定义

```java
// 这些常量在 bathis 项目中广泛使用
SysConst.SUCCESS_CODE  // "T"
SysConst.FAIL_CODE     // "F"
SysConst.MEDITEMTYPE_* // "0"-"7" 项目类型
SYFW_MZ = "0"          // 门诊使用范围
YP_WPBZ_WP = "1"       // 药品-药品标志
```

## 8. verify 模式

### 验证调用次数

```java
verify(mapper).insertSomething(any());           // 恰好调用1次
verify(mapper, never()).deleteSomething(any());  // 从未调用
verify(mapper, times(2)).updateSomething(any()); // 调用2次
verify(mapper, atLeastOnce()).querySomething(any()); // 至少1次
```

### ArgumentCaptor 捕获参数

```java
ArgumentCaptor<RegistrationInfoDO> captor = ArgumentCaptor.forClass(RegistrationInfoDO.class);
verify(mapper).save(captor.capture());
assertEquals("expected", captor.getValue().getField());
```

### argThat 自定义匹配

```java
verify(mapper).insert(argThat(x -> {
    assertEquals("ORG001", x.getOrgnCode());
    return true;
}));
```

## 9. 异常测试

```java
// ApiException
ApiException ex = assertThrows(ApiException.class,
        () -> service.method(args));
assertTrue(ex.getMessage().contains("expected keyword"));

// RuntimeException
RuntimeException ex = assertThrows(RuntimeException.class,
        () -> service.method(args));
```
