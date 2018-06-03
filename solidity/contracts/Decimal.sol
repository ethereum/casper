pragma solidity ^0.4.23;

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

    /** Creates a Decimal Data from a uint. */
    function fromUint(uint num) internal pure returns (Data) {
        return Data({
            num : num,
            den : 1
            });
    }

    /** Converts a Decimal to a uint (effectively flooring the value). **/
    function toUint(Data decimal) internal pure returns (uint) {
        return decimal.num.div(decimal.den);
    }

    /** Adds two Decimals without loss of precision. */
    function add(Data a, Data b) internal pure returns (Data) {

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
    function sub(Data a, Data b) internal pure returns (Data) {

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
    function mul(Data a, Data b) internal pure returns (Data) {
        return Data({
            num : a.num.mul(b.num),
            den : a.den.mul(b.den)
            });
    }

    /** Divides two Decimals without loss of precision. */
    function div(Data a, Data b) internal pure returns (Data) {
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
    function comp(Data a, Data b) internal pure returns (uint8) {
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
    function compZero(Data a) internal pure returns (uint8) {
        if (a.num < 0) {
            return 0;
        } else if (a.num == 0) {
            return 1;
        } else {
            return 2;
        }
    }
}