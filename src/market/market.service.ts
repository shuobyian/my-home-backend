import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Market } from 'src/market/entities/market.entity';
import { DataSource, Repository } from 'typeorm';

@Injectable()
export class MarketService {
  constructor(
    private dataSource: DataSource,
    @InjectRepository(Market) private readonly market: Repository<Market>,
  ) {}

  async findAll() {
    return await this.market.find();
  }

  async findOne(name?: string) {
    return await this.market.find({ where: { name } });
  }
}
