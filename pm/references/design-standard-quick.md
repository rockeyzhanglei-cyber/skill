# WinDesign Next 快速参考指南

> **适用范围**：所有基于 Spark 框架的 Vue3 项目开发
> **组件库**：win-design-next（内部组件库）
> **完整文档**：如需完整 API 文档，请查阅 [design-standard-full.mdc](design-standard-full.mdc)

---

## 组件使用规则（强制）

### 必须遵守

- ✅ **只能使用 win-design-next 组件库**
- ✅ **组件标签必须以 `<w-` 开头（小写）**
- ✅ **框架已全局注册，无需手动导入**

### 严格禁止

- ❌ **使用任何其他 UI 组件库**（如 element-plus、ant-design-vue）
- ❌ **手动注册或导入组件**

### 代码示例

```vue
<template>
  <!-- ✅ 正确：使用 win-design 组件 -->
  <w-button type="primary">提交</w-button>
  <w-input v-model="value" placeholder="请输入" />
  <w-table :data="tableData" :columns="columns" />

  <!-- ❌ 错误：使用其他 UI 库 -->
  <el-button>提交</el-button>
  <a-input v-model:value="value" />
</template>

<script setup lang="ts">
// ✅ 正确：无需导入，开箱即用
// ❌ 错误：禁止手动导入
// import { WButton } from 'win-design-next';
</script>
```

---

## 设计规范

### 设计稿尺寸

| 类型 | 尺寸 |
|------|------|
| **标准尺寸** | 1920 × 1080px |
| **最小适配** | 1366 × 768px |

### 字体规范

| 类型 | 字号 |
|------|------|
| **基础字号** | 14px |
| **小字** | 12px |
| **标题** | 16px |

### 主题色

| 类型 | 颜色值 | CSS 变量 |
|------|--------|----------|
| **主题色** | `#2d5afa` | `--w3-color-primary` |
| **成功色** | `#00ab44` | `--w3-color-success` |
| **警告色** | `#ff8c00` | `--w3-color-warning` |
| **危险色** | `#ec0000` | `--w3-color-danger` |
| **信息色** | `#999999` | `--w3-color-info` |

### 间距规范

使用 `16px` `12px` `8px` `4px` 四档间距

---

## 常用组件速查

### Button 按钮

**常用属性**：

| 属性 | 说明 | 类型 | 默认值 |
|------|------|------|--------|
| `type` | 按钮类型 | `'primary' \| 'success' \| 'warning' \| 'danger' \| 'info'` | — |
| `size` | 尺寸 | `'large' \| 'default' \| 'small' \| 'mini'` | — |
| `disabled` | 禁用状态 | `boolean` | `false` |
| `loading` | 加载状态 | `boolean` | `false` |
| `plain` | 朴素按钮 | `boolean` | `false` |
| `round` | 圆角按钮 | `boolean` | `false` |
| `circle` | 圆形按钮 | `boolean` | `false` |
| `icon` | 图标组件 | `string \| Component` | — |

**示例**：
```vue
<w-button type="primary">主要按钮</w-button>
<w-button type="success" plain>成功按钮</w-button>
<w-button type="danger" :loading="loading">加载中</w-button>
<w-button :icon="Search" circle />
```

---

### Input 输入框

**常用属性**：

| 属性 | 说明 | 类型 | 默认值 |
|------|------|------|--------|
| `v-model` | 绑定值 | `string \| number` | — |
| `type` | 输入框类型 | `'text' \| 'password' \| 'textarea'` | `'text'` |
| `placeholder` | 占位文本 | `string` | — |
| `disabled` | 禁用状态 | `boolean` | `false` |
| `clearable` | 可清空 | `boolean` | `false` |
| `maxlength` | 最大输入长度 | `number` | — |
| `show-word-limit` | 显示字数统计 | `boolean` | `false` |

**常用事件**：

| 事件名 | 说明 | 回调参数 |
|--------|------|----------|
| `input` | 输入时触发 | `(value: string \| number)` |
| `change` | 值改变时触发 | `(value: string \| number)` |
| `focus` | 获得焦点时触发 | `(event: FocusEvent)` |
| `blur` | 失去焦点时触发 | `(event: FocusEvent)` |
| `clear` | 清空时触发 | — |

**示例**：
```vue
<w-input v-model="input" placeholder="请输入内容" clearable />
<w-input type="textarea" v-model="content" :rows="4" maxlength="200" show-word-limit />
<w-input type="password" v-model="password" show-password />
```

---

### Select 选择器

**常用属性**：

| 属性 | 说明 | 类型 | 默认值 |
|------|------|------|--------|
| `v-model` | 绑定值 | `string \| number \| boolean \| object \| array` | — |
| `multiple` | 是否多选 | `boolean` | `false` |
| `disabled` | 禁用状态 | `boolean` | `false` |
| `clearable` | 可清空 | `boolean` | `false` |
| `filterable` | 可搜索 | `boolean` | `false` |
| `placeholder` | 占位文本 | `string` | `'请选择'` |

**子组件**：
- `<w-option>`：选项组件，属性：`label`、`value`、`disabled`
- `<w-option-group>`：选项分组组件

**示例**：
```vue
<w-select v-model="value" placeholder="请选择" clearable>
  <w-option label="选项一" value="1" />
  <w-option label="选项二" value="2" />
  <w-option label="选项三" value="3" />
</w-select>

<!-- 多选 -->
<w-select v-model="values" multiple placeholder="请选择">
  <w-option v-for="item in options" :key="item.value" :label="item.label" :value="item.value" />
</w-select>
```

---

### Table 表格

**常用属性**：

| 属性 | 说明 | 类型 | 默认值 |
|------|------|------|--------|
| `data` | 表格数据 | `array` | `[]` |
| `columns` | 列配置 | `array` | `[]` |
| `height` | 表格高度 | `string \| number` | — |
| `max-height` | 最大高度 | `string \| number` | — |
| `stripe` | 斑马纹 | `boolean` | `false` |
| `border` | 边框 | `boolean` | `false` |
| `row-key` | 行数据的 Key | `string \| Function` | — |
| `show-summary` | 显示合计行 | `boolean` | `false` |

**Column 配置**：

| 属性 | 说明 | 类型 |
|------|------|------|
| `prop` | 字段名 | `string` |
| `label` | 列标题 | `string` |
| `width` | 列宽度 | `string \| number` |
| `min-width` | 最小宽度 | `string \| number` |
| `fixed` | 固定列 | `'left' \| 'right'` |
| `sortable` | 可排序 | `boolean \| 'custom'` |
| `formatter` | 格式化函数 | `Function` |
| `align` | 对齐方式 | `'left' \| 'center' \| 'right'` |

**示例**：
```vue
<template>
  <w-table :data="tableData" :columns="columns" stripe border />
</template>

<script setup lang="ts">
const tableData = [
  { id: 1, name: '张三', age: 28, address: '北京市' },
  { id: 2, name: '李四', age: 32, address: '上海市' },
]

const columns = [
  { prop: 'id', label: 'ID', width: 80 },
  { prop: 'name', label: '姓名', width: 120 },
  { prop: 'age', label: '年龄', width: 80, sortable: true },
  { prop: 'address', label: '地址' },
]
</script>
```

---

### Form 表单

**Form 属性**：

| 属性 | 说明 | 类型 | 默认值 |
|------|------|------|--------|
| `model` | 表单数据对象 | `object` | — |
| `rules` | 表单验证规则 | `object` | — |
| `label-width` | 标签宽度 | `string \| number` | — |
| `label-position` | 标签位置 | `'left' \| 'right' \| 'top'` | `'right'` |
| `inline` | 行内表单 | `boolean` | `false` |
| `disabled` | 禁用所有表单项 | `boolean` | `false` |

**Form-Item 属性**：

| 属性 | 说明 | 类型 | 默认值 |
|------|------|------|--------|
| `prop` | 字段名 | `string` | — |
| `label` | 标签文本 | `string` | — |
| `required` | 是否必填 | `boolean` | `false` |
| `rules` | 验证规则 | `array \| object` | — |

**验证规则**：

```typescript
const rules = {
  name: [
    { required: true, message: '请输入姓名', trigger: 'blur' },
    { min: 2, max: 10, message: '长度在 2 到 10 个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ]
}
```

**示例**：
```vue
<template>
  <w-form ref="formRef" :model="form" :rules="rules" label-width="100px">
    <w-form-item label="姓名" prop="name">
      <w-input v-model="form.name" />
    </w-form-item>
    <w-form-item label="邮箱" prop="email">
      <w-input v-model="form.email" />
    </w-form-item>
    <w-form-item>
      <w-button type="primary" @click="submitForm">提交</w-button>
      <w-button @click="resetForm">重置</w-button>
    </w-form-item>
  </w-form>
</template>
```

---

### DatePicker 日期选择器

**常用属性**：

| 属性 | 说明 | 类型 | 默认值 |
|------|------|------|--------|
| `v-model` | 绑定值 | `string \| Date \| array` | — |
| `type` | 类型 | `'year' \| 'month' \| 'date' \| 'dates' \| 'datetime' \| 'week' \| 'datetimerange' \| 'daterange' \| 'monthrange'` | `'date'` |
| `placeholder` | 占位文本 | `string` | — |
| `format` | 显示格式 | `string` | `'YYYY-MM-DD'` |
| `value-format` | 绑定值格式 | `string` | — |
| `disabled` | 禁用状态 | `boolean` | `false` |
| `clearable` | 可清空 | `boolean` | `true` |
| `range-separator` | 范围分隔符 | `string` | `'至'` |
| `start-placeholder` | 开始占位文本 | `string` | — |
| `end-placeholder` | 结束占位文本 | `string` | — |

**示例**：
```vue
<!-- 日期选择 -->
<w-date-picker v-model="date" type="date" placeholder="选择日期" />

<!-- 日期范围 -->
<w-date-picker
  v-model="dateRange"
  type="daterange"
  range-separator="至"
  start-placeholder="开始日期"
  end-placeholder="结束日期"
/>

<!-- 日期时间 -->
<w-date-picker v-model="datetime" type="datetime" placeholder="选择日期时间" />
```

---

### Dialog 对话框

**常用属性**：

| 属性 | 说明 | 类型 | 默认值 |
|------|------|------|--------|
| `v-model` | 是否显示 | `boolean` | `false` |
| `title` | 标题 | `string` | — |
| `width` | 宽度 | `string \| number` | `'50%'` |
| `fullscreen` | 全屏 | `boolean` | `false` |
| `modal` | 显示遮罩层 | `boolean` | `true` |
| `close-on-click-modal` | 点击遮罩关闭 | `boolean` | `true` |
| `destroy-on-close` | 关闭时销毁元素 | `boolean` | `false` |

**示例**：
```vue
<template>
  <w-button @click="dialogVisible = true">打开对话框</w-button>

  <w-dialog v-model="dialogVisible" title="提示" width="30%">
    <span>这是一段内容</span>
    <template #footer>
      <w-button @click="dialogVisible = false">取消</w-button>
      <w-button type="primary" @click="dialogVisible = false">确定</w-button>
    </template>
  </w-dialog>
</template>
```

---

### Message 消息提示

**方法**：

```typescript
import { WMessage } from 'win-design-next'

// 基础用法
WMessage.success('操作成功')
WMessage.warning('警告信息')
WMessage.error('错误信息')
WMessage.info('提示信息')

// 配置项
WMessage({
  message: '这是一条消息',
  type: 'success',
  duration: 3000,
  showClose: true
})
```

---

### 常用图标

从 `@win-design-next/icons-vue` 导入图标：

```typescript
import {
  Search,      // 搜索
  Edit,        // 编辑
  Delete,      // 删除
  Check,       // 勾选
  Close,       // 关闭
  Plus,        // 添加
  Minus,       // 减少
  Download,    // 下载
  Upload,      // 上传
  Setting,     // 设置
  User,        // 用户
  Date,        // 日期
  Star,        // 星标
  Refresh,     // 刷新
} from '@win-design-next/icons-vue'
```

---

## 完整组件列表

如需以下组件的完整 API 文档，请查阅 [design-standard-full.mdc](design-standard-full.mdc)：

| 组件 | 说明 |
|------|------|
| Autocomplete | 自动补全输入框 |
| Button | 按钮 |
| ButtonGroup | 按钮组 |
| Cascader | 级联选择器 |
| Checkbox | 多选框 |
| DatePicker | 日期选择器 |
| DateTimePicker | 日期时间选择器 |
| Form | 表单 |
| Input | 输入框 |
| InputNumber | 数字输入框 |
| InputTag | 标签输入框 |
| Mention | 提及 |
| Radio | 单选框 |
| Rate | 评分 |
| Select | 选择器 |
| Slider | 滑块 |
| Switch | 开关 |
| Table | 表格 |
| TableSelect | 下拉表格 |
| TimePicker | 时间选择器 |
| TimeSelect | 时间选择 |
| Transfer | 穿梭框 |
| Upload | 上传 |

---

## 最佳实践

### 1. 表单布局

```vue
<w-form :model="form" :rules="rules" label-width="100px" inline>
  <w-form-item label="姓名" prop="name">
    <w-input v-model="form.name" placeholder="请输入姓名" />
  </w-form-item>
  <w-form-item label="部门" prop="dept">
    <w-select v-model="form.dept" placeholder="请选择部门">
      <w-option label="研发部" value="dev" />
      <w-option label="产品部" value="pm" />
    </w-select>
  </w-form-item>
  <w-form-item>
    <w-button type="primary" @click="handleQuery">查询</w-button>
    <w-button @click="handleReset">重置</w-button>
  </w-form-item>
</w-form>
```

### 2. 表格页面

```vue
<template>
  <div class="page-container">
    <!-- 查询区域 -->
    <w-form :model="queryParams" inline>
      <w-form-item label="关键字">
        <w-input v-model="queryParams.keyword" placeholder="请输入关键字" clearable />
      </w-form-item>
      <w-form-item>
        <w-button type="primary" @click="fetchData">查询</w-button>
        <w-button @click="resetQuery">重置</w-button>
      </w-form-item>
    </w-form>

    <!-- 表格区域 -->
    <w-table
      :data="tableData"
      :columns="columns"
      :loading="loading"
      stripe
      border
    />

    <!-- 分页 -->
    <w-pagination
      v-model:current-page="pagination.page"
      v-model:page-size="pagination.size"
      :total="pagination.total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
    />
  </div>
</template>
```

### 3. 禁止事项

```vue
<template>
  <!-- ❌ 错误：使用其他 UI 库 -->
  <el-button>提交</el-button>
  <a-input v-model:value="value" />
  <van-button>按钮</van-button>

  <!-- ❌ 错误：手动导入组件 -->
  <WInput v-model="value" />
</template>

<script setup lang="ts">
// ❌ 错误：手动导入组件
import { WButton } from 'win-design-next'
import { ElInput } from 'element-plus'
</script>
```
