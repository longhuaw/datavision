-- DataVision 数据库初始化脚本
-- 创建数据库（如不存在）
CREATE DATABASE IF NOT EXISTS datavision
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE datavision;

-- 确保 datavision 用户拥有所有权限
GRANT ALL PRIVILEGES ON datavision.* TO 'datavision'@'%';
FLUSH PRIVILEGES;

-- 创建测试数据表（用于演示）
CREATE TABLE IF NOT EXISTS demo_orders (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '订单ID',
    order_no VARCHAR(32) NOT NULL COMMENT '订单号',
    customer_name VARCHAR(64) NOT NULL COMMENT '客户名称',
    category VARCHAR(32) NOT NULL COMMENT '商品品类',
    product_name VARCHAR(128) NOT NULL COMMENT '商品名称',
    quantity INT NOT NULL DEFAULT 1 COMMENT '数量',
    unit_price DECIMAL(10, 2) NOT NULL COMMENT '单价',
    total_amount DECIMAL(12, 2) NOT NULL COMMENT '总金额',
    region VARCHAR(32) NOT NULL COMMENT '地区',
    city VARCHAR(32) NOT NULL COMMENT '城市',
    channel VARCHAR(16) NOT NULL DEFAULT 'online' COMMENT '渠道: online/offline',
    status VARCHAR(16) NOT NULL DEFAULT 'completed' COMMENT '状态: completed/pending/cancelled/refunded',
    order_date DATE NOT NULL COMMENT '订单日期',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='演示订单表';

-- 插入演示数据
INSERT INTO demo_orders (order_no, customer_name, category, product_name, quantity, unit_price, total_amount, region, city, channel, status, order_date) VALUES
('ORD20240001', '张三', '电子产品', 'iPhone 15 Pro', 1, 8999.00, 8999.00, '华东', '上海', 'online', 'completed', '2024-01-15'),
('ORD20240002', '李四', '服装', '羽绒服', 2, 599.00, 1198.00, '华北', '北京', 'online', 'completed', '2024-01-16'),
('ORD20240003', '王五', '食品', '坚果礼盒', 3, 128.00, 384.00, '华南', '深圳', 'online', 'completed', '2024-01-17'),
('ORD20240004', '赵六', '电子产品', 'MacBook Pro', 1, 14999.00, 14999.00, '华东', '杭州', 'offline', 'completed', '2024-01-18'),
('ORD20240005', '孙七', '家居', '乳胶枕', 2, 299.00, 598.00, '西南', '成都', 'online', 'completed', '2024-02-01'),
('ORD20240006', '周八', '服装', '运动鞋', 1, 899.00, 899.00, '华北', '北京', 'online', 'refunded', '2024-02-05'),
('ORD20240007', '吴九', '电子产品', 'AirPods Pro', 1, 1799.00, 1799.00, '华南', '广州', 'online', 'completed', '2024-02-10'),
('ORD20240008', '郑十', '食品', '有机大米', 5, 68.00, 340.00, '华东', '南京', 'offline', 'completed', '2024-02-15'),
('ORD20240009', '冯十一', '家居', '智能台灯', 1, 399.00, 399.00, '华中', '武汉', 'online', 'pending', '2024-03-01'),
('ORD20240010', '陈十二', '电子产品', 'iPad Air', 1, 4799.00, 4799.00, '西南', '重庆', 'online', 'completed', '2024-03-05'),
('ORD20240011', '褚十三', '服装', '牛仔裤', 2, 399.00, 798.00, '东北', '沈阳', 'online', 'completed', '2024-03-10'),
('ORD20240012', '卫十四', '食品', '进口牛排', 1, 258.00, 258.00, '华北', '天津', 'online', 'completed', '2024-03-15'),
('ORD20240013', '蒋十五', '电子产品', '华为Mate 60', 1, 6999.00, 6999.00, '华南', '深圳', 'offline', 'completed', '2024-04-01'),
('ORD20240014', '沈十六', '家居', '记忆棉床垫', 1, 1999.00, 1999.00, '华东', '上海', 'online', 'completed', '2024-04-10'),
('ORD20240015', '韩十七', '食品', '茶叶礼盒', 2, 368.00, 736.00, '西南', '昆明', 'online', 'completed', '2024-04-20'),
('ORD20240016', '杨十八', '服装', '商务衬衫', 3, 299.00, 897.00, '华北', '北京', 'online', 'completed', '2024-05-01'),
('ORD20240017', '朱十九', '电子产品', '小米14 Pro', 1, 4999.00, 4999.00, '华中', '郑州', 'online', 'completed', '2024-05-10'),
('ORD20240018', '秦二十', '家居', '落地灯', 1, 599.00, 599.00, '华南', '广州', 'offline', 'pending', '2024-05-15'),
('ORD20240019', '尤二一', '食品', '巧克力礼盒', 4, 168.00, 672.00, '华东', '苏州', 'online', 'completed', '2024-05-20'),
('ORD20240020', '许二二', '电子产品', '索尼耳机', 1, 2499.00, 2499.00, '东北', '大连', 'online', 'completed', '2024-06-01');

-- 创建演示用户表
CREATE TABLE IF NOT EXISTS demo_users (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
    username VARCHAR(64) NOT NULL COMMENT '用户名',
    email VARCHAR(128) COMMENT '邮箱',
    reg_date DATE NOT NULL COMMENT '注册日期',
    user_level VARCHAR(16) NOT NULL DEFAULT 'normal' COMMENT '用户等级: vip/gold/normal',
    points INT NOT NULL DEFAULT 0 COMMENT '积分',
    region VARCHAR(32) NOT NULL COMMENT '地区',
    status VARCHAR(16) NOT NULL DEFAULT 'active' COMMENT '状态: active/inactive'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='演示用户表';

INSERT INTO demo_users (username, email, reg_date, user_level, points, region, status) VALUES
('张三', 'zhangsan@example.com', '2024-01-10', 'vip', 15000, '华东', 'active'),
('李四', 'lisi@example.com', '2024-01-20', 'gold', 8000, '华北', 'active'),
('王五', 'wangwu@example.com', '2024-02-01', 'normal', 2000, '华南', 'active'),
('赵六', 'zhaoliu@example.com', '2024-02-15', 'gold', 6500, '华东', 'active'),
('孙七', 'sunqi@example.com', '2024-03-01', 'normal', 1200, '西南', 'inactive'),
('周八', 'zhouba@example.com', '2024-03-10', 'vip', 22000, '华北', 'active'),
('吴九', 'wujiu@example.com', '2024-03-20', 'normal', 3000, '华南', 'active'),
('郑十', 'zhengshi@example.com', '2024-04-05', 'gold', 5200, '华东', 'active');
