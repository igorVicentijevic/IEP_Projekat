pragma solidity ^0.8.0;

contract VotingContract {
    address[] public voters;
    uint public approveCount;
    uint public rejectCount;
    bool public ended;
    bool public approved;
    uint public majority;
    mapping(address => bool) public hasVoted;

    constructor(address[] memory _voters) {
        require(_voters.length > 0, "No voters.");
        require(_voters.length % 2 == 1, "Even number of voters.");
        voters = _voters;
        majority = _voters.length / 2 + 1;
    }

    function isVoter(address addr) internal view returns (bool) {
        for (uint i = 0; i < voters.length; i++) {
            if (voters[i] == addr) return true;
        }
        return false;
    }

    function voteApprove() public {
        require(!ended, "Voting ended.");
        require(!hasVoted[msg.sender], "Already voted.");
        require(isVoter(msg.sender), "Invalid address.");
        hasVoted[msg.sender] = true;
        approveCount++;
        if (approveCount >= majority) {
            approved = true;
            ended = true;
        }
    }

    function voteReject() public {
        require(!ended, "Voting ended.");
        require(!hasVoted[msg.sender], "Already voted.");
        require(isVoter(msg.sender), "Invalid address.");
        hasVoted[msg.sender] = true;
        rejectCount++;
        if (rejectCount >= majority) {
            approved = false;
            ended = true;
        }
    }

    function getStatus() public view returns (bool, bool, uint, uint, uint) {
        return (ended, approved, approveCount, rejectCount, majority);
    }
}