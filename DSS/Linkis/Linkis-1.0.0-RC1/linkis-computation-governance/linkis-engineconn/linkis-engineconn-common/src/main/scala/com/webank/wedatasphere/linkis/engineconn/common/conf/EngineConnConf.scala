/*
 * Copyright 2019 WeBank
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.webank.wedatasphere.linkis.engineconn.common.conf

import com.webank.wedatasphere.linkis.common.conf.CommonVars


object EngineConnConf {

  val ENGINE_EXECUTIONS = CommonVars("wds.linkis.engine.connector.executions", "com.webank.wedatasphere.linkis.engineconn.computation.executor.execute.ComputationEngineConnExecution")

  val ENGINE_CONN_HOOKS = CommonVars("wds.linkis.engine.connector.hooks", "com.webank.wedatasphere.linkis.engineconn.computation.executor.hook.ComputationEngineConnHook")


  val ENGINE_LAUNCH_CMD_PARAMS_USER_KEY = CommonVars("wds.linkis.engine.launch.cmd.params.user.key", "user")

  val ENGINE_SUPPORT_PARALLELISM = CommonVars("wds.linkis.engine.parallelism.support.enabled", false)

  val ENGINE_PUSH_LOG_TO_ENTRANCE = CommonVars("wds.linkis.engine.push.log.enable", true)

  val ENGINECONN_PLUGIN_CLAZZ = CommonVars("wds.linkis.engineconn.plugin.default.clazz", "com.webank.wedatasphere.linkis.engineplugin.hive.HiveEngineConnPlugin")


  val ENGINE_TASK_EXPIRE_TIME = CommonVars("wds.linkis.engine.task.expire.time", 1000 * 3600 * 24)

  val ENGINE_LOCK_REFRESH_TIME = CommonVars("wds.linkis.engine.lock.refresh.time", 1000 * 60 * 3)

  val ENGINE_CONN_LOCALPATH_PWD_KEY = CommonVars("wds.linkis.engine.localpath.pwd.key", "PWD")

  val ENGINE_CONN_LOCAL_LOG_DIRS_KEY = CommonVars("wds.linkis.engine.logs.dir.key", "LOG_DIRS")
}
