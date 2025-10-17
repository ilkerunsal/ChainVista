import express from "express";
const app = express(); app.use(express.json());
app.get("/healthz", (req,res)=>res.json({status:"healthy"}));
app.get("/mock/events", (req,res)=>res.json({events:[]}));
app.post("/mock/push", (req,res)=>res.json({status:"stored", received:req.body}));
const port = process.env.PORT || 4000;
app.listen(port, ()=>console.log(`Mock Indexer at http://0.0.0.0:${port}`));
