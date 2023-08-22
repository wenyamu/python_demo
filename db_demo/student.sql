/*
 Navicat Premium Data Transfer

 Source Server         : 70
 Source Server Type    : MySQL
 Source Server Version : 50725
 Source Host           : hdm705192207.my3w.com:3306
 Source Schema         : hdm705192207_db

 Target Server Type    : MySQL
 Target Server Version : 50725
 File Encoding         : 65001

 Date: 15/08/2023 21:55:18
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for student
-- ----------------------------
DROP TABLE IF EXISTS `student`;
CREATE TABLE `student`  (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(5) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL COMMENT '姓名',
  `sex` varchar(2) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL COMMENT '性别',
  `minzu` varchar(2) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL COMMENT '民族',
  `danwei` varchar(10) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL COMMENT '单位',
  `phone` varchar(11) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL COMMENT '手机号',
  `home` int(6) NOT NULL COMMENT '房号',
  `date_time` datetime NOT NULL COMMENT '时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `id`(`id`) USING BTREE
) ENGINE = MyISAM AUTO_INCREMENT = 82 CHARACTER SET = utf8 COLLATE = utf8_general_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of student
-- ----------------------------
INSERT INTO `student` VALUES (61, '李四', '', '', '', '', 111, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (53, '李四', '', '', '', '', 111, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (54, '李四2', '', '', '', '', 111222, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (55, '5', '', '', '', '', 55, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (56, '6', '', '', '', '', 66, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (57, '7', '', '', '', '', 77, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (58, '8', '', '', '', '', 88, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (59, '9', '', '', '', '', 99, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (60, '10', '', '', '', '', 1010, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (62, '2', '', '', '', '', 22, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (63, '张三', '', '', '', '', 222, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (64, '张三', '', '', '', '', 222, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (65, '张三', '', '', '', '', 222, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (66, '张三', '', '', '', '', 222, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (67, '张三', '', '', '', '', 222888, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (68, '张三', '', '', '', '', 222888, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (69, '张三', '', '', '', '', 222888, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (70, '张三', '', '', '', '', 222888, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (71, '张三', '', '', '', '', 222888, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (72, '1', '', '', '', '', 11, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (73, '2', '', '', '', '', 22, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (74, '3', '', '', '', '', 33, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (75, '4', '', '', '', '', 44, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (76, '5', '', '', '', '', 55, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (77, '6', '', '', '', '', 66, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (78, '7', '', '', '', '', 77, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (79, '8', '', '', '', '', 88, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (80, '9', '', '', '', '', 99, '0000-00-00 00:00:00');
INSERT INTO `student` VALUES (81, '10', '', '', '', '', 1010, '0000-00-00 00:00:00');

SET FOREIGN_KEY_CHECKS = 1;
