pragma solidity ^0.4.24;

import './SafeMath.sol';

/**
presented by: https://github.com/raineorshine/sol-decimal

A Solidity Decimal type.

Usage:
import "./Decimal.sol";
contract A {
  using Decimal for Decimal.Data;

  function foo() public constant returns(uint) {
    Decimal.Data memory a = Decimal.fromUint(5);
    Decimal.Data memory b = Decimal.Data({
      num: 12,
      den: 3
    });

    return a.add(b).toUint(); // 9
  }
}

*/
library Decimal {

    using SafeMath for uint256;

    /** Creates a Decimal Data from a uint numerator and uint denominator by directly constructing Data. */
    struct Data {
        uint num; // numerator
        uint den; // denomenator
    }

    // A decimal value can store multiples of 1/DECIMAL_DIVISOR
    uint256 public constant DECIMAL_DIVISOR = 10 ** 10;

    /** Creates a Decimal Data from a uint. */
    function fromUint(uint256 num) internal pure returns (Data memory) {
        return Data({
            num : num,
            den : 1
            });
    }

    /** Creates a Decimal Data from a Decimal bytes. */
    function fromDecimal(uint256 num) internal pure returns (Data memory) {
        return Data({
            num : num,
            den : DECIMAL_DIVISOR
            });
    }

    /** Converts a Decimal to a uint (effectively flooring the value). **/
    function toUint(Data memory self) internal pure returns (uint256) {
        require(self.den > 0, "invalid zero divide.");
        return self.num.div(self.den);
    }

    /** Converts to decimal by increasing up 10 digitsnum. the decimal is fi168x10 **/
    function toDecimal(Data memory self) internal pure returns (uint168) {
        require(self.den > 0, "invalid zero divide.");
        return uint168(self.num.mul(DECIMAL_DIVISOR).div(self.den));
    }

    /** Adds two Decimals without loss of precision. */
    function add(Data memory a, Data memory b) internal pure returns (Data memory) {

        return a.den == b.den ?
        // if same denomenator, use b.num as-is
        Data({
            num : a.num.add(b.num),
            den : a.den
            }) :
        // otherwise convert (b) to the same denominator as (a)
        Data({
            num : a.num.mul(b.den)
            .add(b.num.mul(a.den)),
            den : a.den * b.den
            });
    }

    /** Subtracts two Decimals without loss of precision. */
    function sub(Data memory a, Data memory b) internal pure returns (Data memory) {
        return a.den == b.den ?
        // if same denomenator, use b.num as-is
        Data({
            num : a.num.sub(b.num),
            den : a.den
            }) :
        // otherwise convert (b) to the same denominator as (a)
        Data({
            num : a.num.mul(b.den)
            .sub(b.num.mul(a.den)),
            den : a.den * b.den
            });
    }

    /** Multiplies two Decimals without loss of precision. */
    function mul(Data memory a, Data memory b) internal pure returns (Data memory) {
        return Data({
            num : a.num.mul(b.num),
            den : a.den.mul(b.den)
            });
    }

    /** Divides two Decimals without loss of precision. */
    function div(Data memory a, Data memory b) internal pure returns (Data memory) {
        return Data({
            num : a.num.mul(b.den),
            den : b.num.mul(a.den)
            });
    }

    /**
     * @dev Compare a to b.
     * @return 0 is a < b
     *         1 is a = b
     *         2 is a > b
     */
    function comp(Data memory a, Data memory b) internal pure returns (uint8) {
        uint a_num = a.num * b.den;
        uint b_num = b.num * a.den;
        if (a_num < b_num) {
            return 0;
        } else if (a_num == b_num) {
            return 1;
        } else {
            return 2;
        }
    }

    /**
     * @dev Compare a to 0.
     * @return 0 is a < 0
     *         1 is a = 0
     *         2 is a > 0
     */
    function compZero(Data memory a) internal pure returns (uint8) {
        if (a.num < 0) {
            return 0;
        } else if (a.num == 0) {
            return 1;
        } else {
            return 2;
        }
    }
}