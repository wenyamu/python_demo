
--
-- 表的结构 `student`
--

CREATE TABLE IF NOT EXISTS `student` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(5) NOT NULL COMMENT '姓名',
  `sex` varchar(2) NOT NULL COMMENT '性别',
  `minzu` varchar(2) NOT NULL COMMENT '民族',
  `danwei` varchar(10) NOT NULL COMMENT '单位',
  `phone` varchar(11) NOT NULL COMMENT '手机号',
  `home` varchar(6) NOT NULL COMMENT '房号',
  `date_time` datetime NOT NULL COMMENT '时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `phone` (`phone`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

--
-- 转存表中的数据 `student`
--

INSERT INTO `student` (`name`, `sex`, `minzu`, `danwei`, `phone`, `home`, `date_time`) VALUES
('小刘', '男', '汉', '豫', '15800000000', '111', '2021-11-11 12:12:12');