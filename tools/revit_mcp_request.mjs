// Local prototype: installed server and SDK paths are specific to this workstation.
import fs from 'node:fs';
import {Client} from 'file:///C:/Users/artsafro/INTERACTIVE_TOUR/RevitMCPServer/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js';
import {StdioClientTransport} from 'file:///C:/Users/artsafro/INTERACTIVE_TOUR/RevitMCPServer/node_modules/@modelcontextprotocol/sdk/dist/esm/client/stdio.js';
const [kind,inputFile,outputFile]=process.argv.slice(2);
const server=kind==='pipe'?'C:/Users/artsafro/Desktop/zavod/projects/revit-bridge/src/RevitBridge.McpServer/src/index.js':'C:/Users/artsafro/INTERACTIVE_TOUR/RevitMCPServer/dist/index.js';
const client=new Client({name:'digital-twin-floor',version:'0.1.0'});
await client.connect(new StdioClientTransport({command:process.execPath,args:[server],env:{...process.env,REVIT_MCP_VERSION:'2025',REVIT_MCP_PORT:'7891'},stderr:'pipe'}));
try {
  const req=JSON.parse(fs.readFileSync(inputFile,'utf8').replace(/^\uFEFF/,''));
  const result=req.list?await client.listTools():await client.callTool(req,undefined,{timeout:240000});
  fs.writeFileSync(outputFile,JSON.stringify(result,null,2));
  console.log(JSON.stringify({isError:result.isError||false,output:outputFile,contentTypes:(result.content||[]).map(c=>c.type)}));
}finally{await client.close();}
