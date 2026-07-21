# win-design 组件库使用规范

> win-design 是项目指定的 UI 组件库，所有组件必须使用 `<w-*>` 标签形式。

## 目录

- [基本规则](#基本规则)
- [常用组件](#常用组件)
- [表单组件](#表单组件)
- [数据展示组件](#数据展示组件)
- [反馈组件](#反馈组件)
- [布局组件](#布局组件)
- [最佳实践](#最佳实践)

---

## 基本规则

### 导入方式

```vue
<script setup lang="ts">
// ✅ 正确：无需导入，开箱即用
// win-design 组件已全局注册

// ❌ 错误：禁止手动导入
import { WButton } from 'win-design';
</script>

<template>
  <!-- ✅ 正确：小写 w- 前缀 -->
  <w-button>提交</w-button>

  <!-- ❌ 错误：大写标签 -->
  <W-Button>提交</W-Button>

  <!-- ❌ 错误：使用其他 UI 库 -->
  <el-button>提交</el-button>
  <a-button>提交</a-button>
</template>
```

### 组件命名规范

| 组件类型 | 标签格式 | 示例 |
|---------|---------|------|
| 基础组件 | `<w-*>` | `<w-button>` |
| 表单组件 | `<w-*>` | `<w-input>` |
| 数据组件 | `<w-*>` | `<w-table>` |
| 布局组件 | `<w-*>` | `<w-row>` |

---

## 常用组件

### Button 按钮

```vue
<template>
  <!-- 按钮类型 -->
  <w-button type="primary">主要按钮</w-button>
  <w-button type="success">成功按钮</w-button>
  <w-button type="warning">警告按钮</w-button>
  <w-button type="danger">危险按钮</w-button>
  <w-button type="info">信息按钮</w-button>
  <w-button>默认按钮</w-button>

  <!-- 按钮尺寸 -->
  <w-button size="large">大型按钮</w-button>
  <w-button size="default">默认按钮</w-button>
  <w-button size="small">小型按钮</w-button>

  <!-- 禁用状态 -->
  <w-button disabled>禁用按钮</w-button>

  <!-- 加载状态 -->
  <w-button :loading="loading">加载中</w-button>

  <!-- 图标按钮 -->
  <w-button icon="search">搜索</w-button>

  <!-- 文本按钮 -->
  <w-button type="text">文本按钮</w-button>
  <w-button type="primary" link>链接按钮</w-button>

  <!-- 按钮组 -->
  <w-button-group>
    <w-button>上一页</w-button>
    <w-button>下一页</w-button>
  </w-button-group>
</template>
```

### Icon 图标

```vue
<template>
  <!-- 使用图标名 -->
  <w-icon name="edit" />
  <w-icon name="delete" />
  <w-icon name="search" />

  <!-- 图标尺寸 -->
  <w-icon name="edit" :size="20" />
  <w-icon name="edit" size="24px" />

  <!-- 图标颜色 -->
  <w-icon name="edit" color="#409EFC" />

  <!-- 在按钮中使用 -->
  <w-button :icon="Edit">编辑</w-button>
</template>
```

---

## 表单组件

### Input 输入框

```vue
<template>
  <!-- 基础输入框 -->
  <w-input v-model="value" placeholder="请输入" />

  <!-- 禁用状态 -->
  <w-input v-model="value" disabled />

  <!-- 只读状态 -->
  <w-input v-model="value" readonly />

  <!-- 可清空 -->
  <w-input v-model="value" clearable />

  <!-- 密码输入框 -->
  <w-input v-model="password" type="password" show-password />

  <!-- 文本域 -->
  <w-input
    v-model="content"
    type="textarea"
    :rows="4"
    placeholder="请输入内容"
  />

  <!-- 带前缀/后缀 -->
  <w-input v-model="url" placeholder="请输入网址">
    <template #prepend>https://</template>
    <template #append>.com</template>
  </w-input>

  <!-- 带图标 -->
  <w-input v-model="search" prefix-icon="search" />
  <w-input v-model="search" suffix-icon="calendar" />

  <!-- 输入长度限制 -->
  <w-input v-model="value" maxlength="20" show-word-limit />
</template>
```

### Select 选择器

```vue
<template>
  <!-- 基础选择器 -->
  <w-select v-model="value" placeholder="请选择">
    <w-option label="选项一" value="1" />
    <w-option label="选项二" value="2" />
    <w-option label="选项三" value="3" />
  </w-select>

  <!-- 禁用选项 -->
  <w-select v-model="value" placeholder="请选择">
    <w-option label="选项一" value="1" />
    <w-option label="选项二" value="2" disabled />
    <w-option label="选项三" value="3" />
  </w-select>

  <!-- 多选 -->
  <w-select v-model="values" multiple placeholder="请选择">
    <w-option label="选项一" value="1" />
    <w-option label="选项二" value="2" />
    <w-option label="选项三" value="3" />
  </w-select>

  <!-- 可搜索 -->
  <w-select v-model="value" filterable placeholder="请选择">
    <w-option
      v-for="item in options"
      :key="item.value"
      :label="item.label"
      :value="item.value"
    />
  </w-select>

  <!-- 分组 -->
  <w-select v-model="value" placeholder="请选择">
    <w-option-group label="热门城市">
      <w-option label="北京" value="beijing" />
      <w-option label="上海" value="shanghai" />
    </w-option-group>
    <w-option-group label="其他城市">
      <w-option label="杭州" value="hangzhou" />
      <w-option label="深圳" value="shenzhen" />
    </w-option-group>
  </w-select>

  <!-- 远程搜索 -->
  <w-select
    v-model="value"
    filterable
    remote
    :remote-method="remoteMethod"
    :loading="loading"
  >
    <w-option
      v-for="item in options"
      :key="item.value"
      :label="item.label"
      :value="item.value"
    />
  </w-select>
</template>

<script setup lang="ts">
import { ref } from 'spark';

const value = ref('');
const values = ref<string[]>([]);
const loading = ref(false);
const options = ref<Option[]>([]);

const remoteMethod = async (query: string) => {
  if (query) {
    loading.value = true;
    // 调用 API 搜索
    options.value = await searchOptions(query);
    loading.value = false;
  }
};
</script>
```

### Radio 单选框

```vue
<template>
  <!-- 基础单选框 -->
  <w-radio-group v-model="value">
    <w-radio label="1">选项一</w-radio>
    <w-radio label="2">选项二</w-radio>
    <w-radio label="3">选项三</w-radio>
  </w-radio-group>

  <!-- 按钮样式 -->
  <w-radio-group v-model="value">
    <w-radio-button label="1">选项一</w-radio-button>
    <w-radio-button label="2">选项二</w-radio-button>
    <w-radio-button label="3">选项三</w-radio-button>
  </w-radio-group>

  <!-- 禁用状态 -->
  <w-radio-group v-model="value">
    <w-radio label="1" disabled>选项一</w-radio>
    <w-radio label="2">选项二</w-radio>
  </w-radio-group>
</template>
```

### Checkbox 复选框

```vue
<template>
  <!-- 基础复选框 -->
  <w-checkbox-group v-model="values">
    <w-checkbox label="1">选项一</w-checkbox>
    <w-checkbox label="2">选项二</w-checkbox>
    <w-checkbox label="3">选项三</w-checkbox>
  </w-checkbox-group>

  <!-- 按钮样式 -->
  <w-checkbox-group v-model="values">
    <w-checkbox-button label="1">选项一</w-checkbox-button>
    <w-checkbox-button label="2">选项二</w-checkbox-button>
    <w-checkbox-button label="3">选项三</w-checkbox-button>
  </w-checkbox-group>

  <!-- 全选 -->
  <w-checkbox
    v-model="checkAll"
    :indeterminate="isIndeterminate"
    @change="handleCheckAllChange"
  >
    全选
  </w-checkbox>
</template>
```

### DatePicker 日期选择器

```vue
<template>
  <!-- 日期选择 -->
  <w-date-picker
    v-model="date"
    type="date"
    placeholder="选择日期"
  />

  <!-- 日期时间选择 -->
  <w-date-picker
    v-model="datetime"
    type="datetime"
    placeholder="选择日期时间"
  />

  <!-- 日期范围 -->
  <w-date-picker
    v-model="dateRange"
    type="daterange"
    range-separator="至"
    start-placeholder="开始日期"
    end-placeholder="结束日期"
  />

  <!-- 日期时间范围 -->
  <w-date-picker
    v-model="datetimeRange"
    type="datetimerange"
    range-separator="至"
    start-placeholder="开始时间"
    end-placeholder="结束时间"
  />

  <!-- 带快捷选项 -->
  <w-date-picker
    v-model="date"
    type="date"
    placeholder="选择日期"
    :shortcuts="shortcuts"
  />

  <!-- 禁用日期 -->
  <w-date-picker
    v-model="date"
    type="date"
    placeholder="选择日期"
    :disabled-date="disabledDate"
  />
</template>

<script setup lang="ts">
import { ref } from 'spark';

const date = ref('');
const datetime = ref('');
const dateRange = ref([]);
const datetimeRange = ref([]);

const shortcuts = [
  {
    text: '今天',
    value: new Date(),
  },
  {
    text: '昨天',
    value: () => {
      const date = new Date();
      date.setTime(date.getTime() - 3600 * 1000 * 24);
      return date;
    },
  },
  {
    text: '一周前',
    value: () => {
      const date = new Date();
      date.setTime(date.getTime() - 3600 * 1000 * 24 * 7);
      return date;
    },
  },
];

const disabledDate = (time: Date) => {
  return time.getTime() > Date.now();
};
</script>
```

### Form 表单

```vue
<template>
  <w-form
    ref="formRef"
    :model="formData"
    :rules="rules"
    label-width="100px"
  >
    <w-form-item label="用户名" prop="username">
      <w-input v-model="formData.username" />
    </w-form-item>

    <w-form-item label="密码" prop="password">
      <w-input v-model="formData.password" type="password" />
    </w-form-item>

    <w-form-item label="邮箱" prop="email">
      <w-input v-model="formData.email" />
    </w-form-item>

    <w-form-item label="手机号" prop="phone">
      <w-input v-model="formData.phone" />
    </w-form-item>

    <w-form-item>
      <w-button type="primary" @click="handleSubmit">提交</w-button>
      <w-button @click="handleReset">重置</w-button>
    </w-form-item>
  </w-form>
</template>

<script setup lang="ts">
import { ref, reactive } from 'spark';
import type { FormInstance, FormRules } from 'spark';

const formRef = ref<FormInstance>();

const formData = reactive({
  username: '',
  password: '',
  email: '',
  phone: ''
});

const rules = reactive<FormRules>({
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '长度在 3 到 20 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 20, message: '长度在 6 到 20 个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
  ],
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }
  ]
});

const handleSubmit = async () => {
  if (!formRef.value) return;

  await formRef.value.validate((valid) => {
    if (valid) {
      // 提交表单
      console.log('提交', formData);
    }
  });
};

const handleReset = () => {
  formRef.value?.resetFields();
};
</script>
```

---

## 数据展示组件

### Table 表格

```vue
<template>
  <w-table
    :data="tableData"
    :loading="loading"
    stripe
    border
    style="width: 100%"
  >
    <!-- 选择列 -->
    <w-table-column type="selection" width="55" />

    <!-- 序号列 -->
    <w-table-column type="index" label="序号" width="60" />

    <!-- 普通列 -->
    <w-table-column prop="name" label="姓名" width="120" />

    <!-- 自定义列 -->
    <w-table-column prop="status" label="状态" width="100">
      <template #default="{ row }">
        <w-tag :type="row.status === 'active' ? 'success' : 'danger'">
          {{ row.status === 'active' ? '启用' : '禁用' }}
        </w-tag>
      </template>
    </w-table-column>

    <!-- 操作列 -->
    <w-table-column label="操作" width="200">
      <template #default="{ row }">
        <w-button size="small" @click="handleEdit(row)">编辑</w-button>
        <w-button size="small" type="danger" @click="handleDelete(row)">
          删除
        </w-button>
      </template>
    </w-table-column>
  </w-table>

  <!-- 分页 -->
  <w-pagination
    v-model:current-page="currentPage"
    v-model:page-size="pageSize"
    :total="total"
    :page-sizes="[10, 20, 50, 100]"
    layout="total, sizes, prev, pager, next, jumper"
    @size-change="handleSizeChange"
    @current-change="handleCurrentChange"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'spark';

const loading = ref(false);
const tableData = ref<User[]>([]);
const currentPage = ref(1);
const pageSize = ref(10);
const total = ref(0);

const fetchData = async () => {
  loading.value = true;
  try {
    const res = await userApi.getList({
      page: currentPage.value,
      pageSize: pageSize.value
    });
    tableData.value = res.data;
    total.value = res.total;
  } finally {
    loading.value = false;
  }
};

const handleSizeChange = (val: number) => {
  pageSize.value = val;
  fetchData();
};

const handleCurrentChange = (val: number) => {
  currentPage.value = val;
  fetchData();
};

onMounted(() => {
  fetchData();
});
</script>
```

### Tree 树形控件

```vue
<template>
  <!-- 基础树形控件 -->
  <w-tree
    :data="treeData"
    :props="defaultProps"
    @node-click="handleNodeClick"
  />

  <!-- 可选择 -->
  <w-tree
    :data="treeData"
    show-checkbox
    :default-checked-keys="checkedKeys"
    @check="handleCheck"
  />

  <!-- 可搜索 -->
  <w-input v-model="filterText" placeholder="输入关键字筛选" />
  <w-tree
    :data="treeData"
    :filter-node-method="filterNode"
    ref="treeRef"
  />

  <!-- 懒加载 -->
  <w-tree
    :props="props"
    :load="loadNode"
    lazy
  />
</template>

<script setup lang="ts">
import { ref, watch } from 'spark';
import type { TreeInstance } from 'spark';

const treeRef = ref<TreeInstance>();
const filterText = ref('');

const defaultProps = {
  children: 'children',
  label: 'label'
};

watch(filterText, (val) => {
  treeRef.value?.filter(val);
});

const filterNode = (value: string, data: TreeNode) => {
  if (!value) return true;
  return data.label.includes(value);
};

const loadNode = async (node: any, resolve: Function) => {
  if (node.level === 0) {
    const data = await fetchRootNodes();
    resolve(data);
  } else {
    const data = await fetchChildNodes(node.data.id);
    resolve(data);
  }
};
</script>
```

### Tag 标签

```vue
<template>
  <!-- 标签类型 -->
  <w-tag>默认标签</w-tag>
  <w-tag type="success">成功标签</w-tag>
  <w-tag type="warning">警告标签</w-tag>
  <w-tag type="danger">危险标签</w-tag>
  <w-tag type="info">信息标签</w-tag>

  <!-- 可移除标签 -->
  <w-tag
    v-for="tag in tags"
    :key="tag"
    closable
    @close="handleClose(tag)"
  >
    {{ tag }}
  </w-tag>

  <!-- 可编辑标签 -->
  <w-tag
    v-for="tag in dynamicTags"
    :key="tag"
    closable
    :disable-transitions="false"
    @close="handleClose(tag)"
  >
    {{ tag }}
  </w-tag>
  <w-input
    v-if="inputVisible"
    ref="inputRef"
    v-model="inputValue"
    size="small"
    @keyup.enter="handleInputConfirm"
    @blur="handleInputConfirm"
  />
  <w-button v-else size="small" @click="showInput">+ 新标签</w-button>
</template>
```

---

## 反馈组件

### Message 消息提示

```typescript
import { Message } from 'spark';

// 成功消息
Message.success('操作成功');

// 警告消息
Message.warning('请注意');

// 错误消息
Message.error('操作失败');

// 信息消息
Message.info('提示信息');

// 可关闭的消息
Message({
  message: '这是一条消息',
  type: 'success',
  showClose: true,
  duration: 3000
});

// 使用 VNode
Message({
  dangerouslyUseHTMLString: true,
  message: '<strong>这是 <i>HTML</i> 片段</strong>'
});
```

### MessageBox 消息弹框

```typescript
import { MessageBox } from 'spark';

// 确认框
const confirm = async () => {
  try {
    await MessageBox.confirm('确定要删除吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    });
    // 用户点击了确定
    deleteItem();
  } catch {
    // 用户点击了取消
    console.log('取消删除');
  }
};

// 提示框
const alert = async () => {
  await MessageBox.alert('这是一条提示信息', '提示', {
    confirmButtonText: '确定'
  });
};

// 输入框
const prompt = async () => {
  try {
    const { value } = await MessageBox.prompt('请输入邮箱', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPattern: /[\w!#$%&'*+/=?^_`{|}~-]+(?:\.[\w!#$%&'*+/=?^_`{|}~-]+)*@(?:[\w](?:[\w-]*[\w])?\.)+[\w](?:[\w-]*[\w])?/,
      inputErrorMessage: '邮箱格式不正确'
    });
    console.log('输入的邮箱:', value);
  } catch {
    console.log('取消输入');
  }
};
```

### Dialog 对话框

```vue
<template>
  <w-button @click="dialogVisible = true">打开对话框</w-button>

  <w-dialog
    v-model="dialogVisible"
    title="对话框标题"
    width="50%"
    :before-close="handleClose"
  >
    <span>这是一段内容</span>

    <template #footer>
      <w-button @click="dialogVisible = false">取消</w-button>
      <w-button type="primary" @click="handleConfirm">确定</w-button>
    </template>
  </w-dialog>
</template>

<script setup lang="ts">
import { ref } from 'spark';
import { MessageBox } from 'spark';

const dialogVisible = ref(false);

const handleClose = (done: () => void) => {
  MessageBox.confirm('确定要关闭吗？')
    .then(() => {
      done();
    })
    .catch(() => {
      // 取消关闭
    });
};

const handleConfirm = () => {
  // 处理确认逻辑
  dialogVisible.value = false;
};
</script>
```

### Loading 加载

```vue
<template>
  <!-- 指令方式 -->
  <div v-loading="loading" element-loading-text="加载中...">
    <!-- 内容 -->
  </div>

  <!-- 服务方式 -->
  <w-button @click="openLoading">显示加载</w-button>
</template>

<script setup lang="ts">
import { ref } from 'spark';
import { Loading } from 'spark';

const loading = ref(false);

const openLoading = () => {
  const loadingInstance = Loading.service({
    lock: true,
    text: '加载中...',
    background: 'rgba(0, 0, 0, 0.7)'
  });

  setTimeout(() => {
    loadingInstance.close();
  }, 2000);
};
</script>
```

---

## 布局组件

### Layout 布局

```vue
<template>
  <!-- 基础布局 -->
  <w-row>
    <w-col :span="24">
      <div class="grid-content">24</div>
    </w-col>
  </w-row>

  <w-row>
    <w-col :span="12">
      <div class="grid-content">12</div>
    </w-col>
    <w-col :span="12">
      <div class="grid-content">12</div>
    </w-col>
  </w-row>

  <w-row :gutter="20">
    <w-col :span="6">
      <div class="grid-content">6</div>
    </w-col>
    <w-col :span="6">
      <div class="grid-content">6</div>
    </w-col>
    <w-col :span="6">
      <div class="grid-content">6</div>
    </w-col>
    <w-col :span="6">
      <div class="grid-content">6</div>
    </w-col>
  </w-row>

  <!-- 响应式布局 -->
  <w-row>
    <w-col :xs="24" :sm="12" :md="8" :lg="6" :xl="4">
      <div class="grid-content">响应式</div>
    </w-col>
  </w-row>

  <!-- 偏移 -->
  <w-row>
    <w-col :span="6" :offset="6">
      <div class="grid-content">offset-6</div>
    </w-col>
  </w-row>
</template>

<style scoped>
.grid-content {
  background: #d3dce6;
  padding: 10px;
  text-align: center;
  border-radius: 4px;
}
</style>
```

### Container 布局容器

```vue
<template>
  <w-container>
    <w-header>Header</w-header>
    <w-container>
      <w-aside width="200px">Aside</w-aside>
      <w-main>Main</w-main>
    </w-container>
    <w-footer>Footer</w-footer>
  </w-container>
</template>

<style scoped>
.w-header,
.w-footer {
  background-color: #b3c0d1;
  color: #333;
  text-align: center;
  line-height: 60px;
}

.w-aside {
  background-color: #d3dce6;
  color: #333;
  text-align: center;
  line-height: 200px;
}

.w-main {
  background-color: #e9eef3;
  color: #333;
  text-align: center;
  line-height: 160px;
}
</style>
```

---

## 最佳实践

### 1. 表单验证

```typescript
// 定义验证规则
const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '长度在 3 到 20 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { validator: validatePassword, trigger: 'blur' }
  ]
};

// 自定义验证器
const validatePassword = (rule: any, value: string, callback: any) => {
  if (!value) {
    callback(new Error('请输入密码'));
  } else if (value.length < 6) {
    callback(new Error('密码长度不能少于6位'));
  } else {
    callback();
  }
};
```

### 2. 表格分页

```typescript
// 使用组合式函数封装
export function useTable<T>(fetchFn: (params: any) => Promise<any>) {
  const loading = ref(false);
  const data = ref<T[]>([]);
  const total = ref(0);
  const currentPage = ref(1);
  const pageSize = ref(10);

  const fetchData = async () => {
    loading.value = true;
    try {
      const res = await fetchFn({
        page: currentPage.value,
        pageSize: pageSize.value
      });
      data.value = res.data;
      total.value = res.total;
    } finally {
      loading.value = false;
    }
  };

  const handleSizeChange = (val: number) => {
    pageSize.value = val;
    fetchData();
  };

  const handleCurrentChange = (val: number) => {
    currentPage.value = val;
    fetchData();
  };

  return {
    loading,
    data,
    total,
    currentPage,
    pageSize,
    fetchData,
    handleSizeChange,
    handleCurrentChange
  };
}
```

### 3. 弹窗封装

```typescript
// 使用组合式函数封装弹窗逻辑
export function useDialog() {
  const visible = ref(false);
  const mode = ref<'add' | 'edit'>('add');
  const data = ref<any>(null);

  const open = (newMode: 'add' | 'edit', rowData?: any) => {
    mode.value = newMode;
    data.value = rowData ? { ...rowData } : null;
    visible.value = true;
  };

  const close = () => {
    visible.value = false;
    data.value = null;
  };

  return {
    visible,
    mode,
    data,
    open,
    close
  };
}
```

### 4. 样式深度选择器

```vue
<style scoped>
/* Vue 3 深度选择器 */
:deep(.w-table .cell) {
  padding: 0;
}

:deep(.w-input__inner) {
  height: 32px;
}

/* 全局样式 */
:global(.custom-class) {
  color: red;
}
</style>
```
