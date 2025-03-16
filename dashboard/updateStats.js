// replace this with your Cloud VM's DNS
const CLOUD_DNS = "127.0.0.1";

const PROCESSING_STATS_API_URL = `http://${CLOUD_DNS}:8100/stats`;
const ANALYZER_API_URL = {
  stats: `http://${CLOUD_DNS}:8200/stats`,
  attr_info: `http://${CLOUD_DNS}:8200/attr_info`,
  exp_info: `http://${CLOUD_DNS}:8200/exp_info`,
};

// This function fetches and updates the general statistics
const makeReq = (url, cb) => {
  fetch(url)
    .then((res) => res.json())
    .then((result) => {
      console.log("Received data: ", result);
      cb(result);
    })
    .catch((error) => {
      updateErrorMessages(error.message);
    });
};

const getRandomInt = (max) => {
  return Math.floor(Math.random() * max);
}

const makeReqParam = (url, max, cb) => {
  if (url == ANALYZER_API_URL.attr_info) {
    max_sp = max["num_attr"];
  } else {
    max_sp = max["num_exp"];
  }

  fetch(`${url}?index=${getRandomInt(max_sp)}`)
    .then((res) => res.json())
    .then((result) => {
      console.log("Received data: ", result);
      cb(result);
    })
    .catch((error) => {
      updateErrorMessages(error.message);
    });
};

const updateProc = (result) => {
  document.getElementById("proc_num_attr").innerText =
    result["num_attractions"];
  document.getElementById("proc_num_exp").innerText = result["num_expenses"];
  document.getElementById("proc_hours").innerText = result["avg_hours_open"];
  document.getElementById("proc_amount").innerText = result["avg_amount"];
  document.getElementById("proc_last_updated").innerText =
    result["last_updated"];
};

const updateAnSt = (result) => {
  document.getElementById("an_num_attr").innerText = result["num_attr"];
  document.getElementById("an_num_exp").innerText = result["num_exp"];
};

const updateAttr = (result) => {
  document.getElementById("attr_usr").innerText = result["user_id"];
  document.getElementById("attr_cat").innerText = result["attraction_category"];
  document.getElementById("attr_hours").innerText = result["hours_open"];
  document.getElementById("attr_time").innerText =
    result["attraction_timestamp"];
  document.getElementById("attr_trace").innerText = result["trace_id"];
};

const updateExp = (result) => {
  document.getElementById("exp_usr").innerText = result["user_id"];
  document.getElementById("exp_cat").innerText = result["expense_category"];
  document.getElementById("exp_amount").innerText = `${result["amount"]}`;
  document.getElementById("exp_time").innerText = result["expense_timestamp"];
  document.getElementById("exp_trace").innerText = result["trace_id"];
};

const getLocaleDateStr = () => new Date().toLocaleString();

const getStats = () => {
  document.getElementById("last-updated-value").innerText = getLocaleDateStr();

  makeReq(PROCESSING_STATS_API_URL, (result) => updateProc(result));
  makeReq(ANALYZER_API_URL.stats, (result) => updateAnSt(result));
  makeReq(ANALYZER_API_URL.stats, (max) =>
    makeReqParam(ANALYZER_API_URL.attr_info, max, (result) =>
      updateAttr(result)
    )
  );
  makeReq(ANALYZER_API_URL.stats, (max) =>
    makeReqParam(ANALYZER_API_URL.exp_info, max, (result) => updateExp(result))
  );
};

const updateErrorMessages = (message) => {
  const id = Date.now();
  console.log("Creation", id);
  msg = document.createElement("div");
  msg.id = `error-${id}`;
  msg.innerHTML = `<p>Something happened at ${getLocaleDateStr()}!</p><code>${message}</code>`;
  document.getElementById("messages").style.display = "block";
  document.getElementById("messages").prepend(msg);
  setTimeout(() => {
    const elem = document.getElementById(`error-${id}`);
    if (elem) {
      elem.remove();
    }
  }, 7000);
};

const setup = () => {
  getStats();
  setInterval(() => getStats(), 4000); // Update every 4 seconds
};

document.addEventListener("DOMContentLoaded", setup);
